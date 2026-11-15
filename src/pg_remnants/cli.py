import argparse
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from .config import load, load_secrets
from .runtime import Collector, read_json
from .service import run


def main() -> int:
    parser = argparse.ArgumentParser(description='Pirate Galaxy Remnant Tracker')
    parser.add_argument('--config', type=Path, default=Path('config.toml'))
    sub = parser.add_subparsers(dest='command', required=True)
    start = sub.add_parser('run')
    start.add_argument('--cycles', type=int, default=0)
    start.add_argument('--max-seconds', type=int, default=0)
    start.add_argument('--dry-run', action='store_true')
    sub.add_parser('validate')
    sub.add_parser('status')
    sub.add_parser('stop')
    args = parser.parse_args()
    try:
        config = load(args.config)
        config.data.mkdir(parents=True, exist_ok=True)
        load_secrets(config.root / 'secrets.env')
        logger = logging.getLogger()
        logger.setLevel(logging.INFO)
        formatter = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
        for handler in (logging.StreamHandler(), RotatingFileHandler(config.data / 'tracker.log', maxBytes=2_000_000, backupCount=3, encoding='utf-8')):
            handler.setFormatter(formatter)
            logger.addHandler(handler)
        if args.command == 'validate':
            Collector(config).prepare()
            print('Configuration, pinned runtime and Java compilation validated')
            return 0
        if args.command == 'status':
            print(json.dumps(read_json(config.data / 'status.json'), ensure_ascii=False, indent=2))
            return 0
        if args.command == 'stop':
            (config.data / 'tracker-stop.request').touch()
            print('Graceful tracker stop requested')
            return 0
        if args.cycles < 0 or args.max_seconds < 0:
            raise ValueError('Run limits must be non-negative')
        return run(config, cycles=args.cycles, dry_run=args.dry_run, max_seconds=args.max_seconds)
    except Exception as error:
        # No arbitrary exception messages/tracebacks: URLs, credentials and native login data stay private.
        logging.error('Operation failed (%s); check configuration and local runtime status', type(error).__name__)
        return 1
