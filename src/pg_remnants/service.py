from __future__ import annotations

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .card import payload
from .config import Config
from .discord import DiscordError, Publisher
from .locking import single_instance
from .model import Snapshot
from .render import render
from .runtime import Collector, atomic_json
from .storage import Store

LOGGER = logging.getLogger(__name__)


def run(config: Config, *, cycles: int = 0, dry_run: bool = False, max_seconds: int = 0) -> int:
    with single_instance(config.data / 'tracker.lock'):
        return _run(config, cycles=cycles, dry_run=dry_run, max_seconds=max_seconds)


def _run(config: Config, *, cycles: int, dry_run: bool, max_seconds: int) -> int:
    store = Store(config.data / 'history.sqlite3', config.poll_seconds)
    collector = Collector(config)
    publishers = {}
    if not dry_run:
        seen = set()
        for name in config.webhook_names:
            publisher = Publisher(os.environ.get(name, ''), store)
            if publisher.target not in seen:
                publishers[name] = publisher
                seen.add(publisher.target)
    snapshot = store.latest(config.realm_id)
    stop_path = config.data / 'tracker-stop.request'
    stop_path.unlink(missing_ok=True)
    started = time.monotonic()
    count, failures, retry_at, last_publish, last_valid = 0, 0, 0.0, started, 0.0
    problem, fatal, active, last_result = 'Verbindung wird aufgebaut', False, False, None
    discord_problem = None
    discord_targets = {}
    status_path = config.data / 'status.json'
    def status(state):
        if state == 'running' and discord_problem:
            state = 'publishing_error'
        atomic_json(status_path, {'state': state, 'pid': os.getpid(), 'updated_ms': int(time.time()*1000),
                                 'snapshots_this_run': count, 'last_observed_ms': snapshot.observed_ms if snapshot else None,
                                 'discord': last_result, 'dry_run': dry_run, 'poll_seconds': config.poll_seconds,
                                 'discord_targets': discord_targets,
                                 'freshness': ('new_session' if snapshot.fresh_session else 'released_graph'
                                               if snapshot.fresh_graph else 'unverified') if snapshot else None,
                                 'problem': problem or discord_problem})
    def publish(reason=None, delta=()):
        nonlocal last_publish, last_result, discord_problem
        now_ms = int(time.time()*1000)
        card = payload(snapshot, server=config.server, username=config.username, poll_seconds=config.poll_seconds,
                       now_ms=now_ms, delta=delta, problem=reason)
        png = render(snapshot, server=config.server, poll_seconds=config.poll_seconds, now_ms=now_ms,
                     problem=reason, history=store.intel_history(snapshot) if snapshot else {},
                     estimates=store.reveal_estimates(snapshot, config.retention_days) if snapshot else {})
        image_path = config.data / 'status-card.png'
        image_path.with_suffix('.tmp').write_bytes(png)
        os.replace(image_path.with_suffix('.tmp'), image_path)
        if publishers:
            # Network requests run independently; SQLite stays on the service thread.
            failed = []
            primary = next(iter(publishers))
            with ThreadPoolExecutor(max_workers=len(publishers)) as pool:
                pending = {pool.submit(p.publish,card,now_ms,image=png,
                                       message_id=store.message(p.target),persist=False): (name,p)
                           for name,p in publishers.items()}
                for future in as_completed(pending):
                    name,publisher = pending[future]
                    try:
                        receipt = future.result()
                    except DiscordError as error:
                        failed.append(name)
                        discord_targets[name] = {'state':'error','attempted_ms':now_ms,
                                                 'last_success':discord_targets.get(name,{}).get('last_success')}
                        LOGGER.error('Discord target %s: %s',name,error)
                        continue
                    store.save_message(publisher.target,receipt['message_id'],receipt['channel_id'],now_ms)
                    receipt.update(published_ms=now_ms,target=name)
                    discord_targets[name] = {'state':'ok','last_success':receipt}
                    if name == primary:
                        last_result = receipt
                    with (config.data / 'publications.jsonl').open('a',encoding='utf-8') as stream:
                        stream.write(json.dumps(receipt)+'\n')
                    LOGGER.info('Discord %s confirmed for target %s',receipt['method'],name)
            discord_problem = f'Discord-Aktualisierung fehlgeschlagen: {len(failed)}/{len(publishers)} Ziele' if failed else None
        else:
            atomic_json(config.data / 'preview.json', card)
            LOGGER.info('Dry run: status card prepared without Discord')
        last_publish = time.monotonic()
    try:
        collector.prepare()
        status('starting')
        while not stop_path.exists():
            now = time.monotonic()
            if max_seconds and now - started >= max_seconds:
                break
            if not active and now >= retry_at:
                collector.start()
                active = True
                LOGGER.info('Headless collector started for realm %d', config.realm_id)
            for event in collector.events() if active else ():
                kind = event.get('event')
                if kind == 'snapshot':
                    candidate = Snapshot.from_event(event, config.realm_id, int(time.time()*1000))
                    if not candidate.verified_fresh:
                        raise ValueError('Collector snapshot lacks verified fresh data')
                    delta = store.record(candidate, config.retention_days)
                    snapshot, last_valid, failures, problem = candidate, now, 0, None
                    count += 1
                    try:
                        publish(delta=delta)
                    except DiscordError as error:
                        LOGGER.error('%s', error)
                    status('running')
                    if cycles and count >= cycles:
                        break
                elif kind == 'failure':
                    problem = 'Verbindung unterbrochen – letzter bestätigter Stand'
                    fatal = bool(event.get('fatal'))
                    LOGGER.warning('Collector failure: %s (fatal=%s)', event.get('type', 'unknown'), fatal)
                elif kind == 'connection_closed' and last_valid:
                    problem = 'Verbindung unterbrochen – letzter bestätigter Stand'
            if cycles and count >= cycles:
                break
            exited = collector.exit_code() if active else None
            overdue = active and now - (last_valid or collector.started) > config.poll_seconds + 90
            if exited is not None or overdue or fatal:
                collector.stop()
                active = False
                failures += 1
                problem = 'Anmeldung/Version prüfen' if fatal else 'Verbindung unterbrochen – erneuter Versuch folgt'
                try:
                    publish(reason=problem)
                except DiscordError as error:
                    LOGGER.error('%s', error)
                status('error' if fatal else 'reconnecting')
                if fatal:
                    return 2
                retry_at = now + min(300, 30 * 2 ** min(failures-1, 4))
                last_valid = 0.0
            elif problem and now - last_publish >= config.poll_seconds:
                try:
                    publish(reason=problem)
                except DiscordError as error:
                    LOGGER.error('%s', error)
                status('reconnecting' if count else 'starting')
            time.sleep(0.25)
        return 0 if count else 1
    except KeyboardInterrupt:
        return 0
    finally:
        collector.stop()
        problem = 'Tracker gestoppt – letzter bestätigter Stand'
        try:
            if discord_targets:
                publish(reason=problem)
        except DiscordError as error:
            LOGGER.error('%s', error)
        status('stopped')
        store.close()
