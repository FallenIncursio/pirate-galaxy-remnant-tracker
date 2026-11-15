"""Keep observed reveals and explicitly labelled historical estimates distinct."""
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from .model import Carrier
from .estimates import Estimate

TIMEZONE = ZoneInfo('Europe/Berlin')


def clock(ms: int, *, date: bool = False) -> str:
    return datetime.fromtimestamp(ms / 1000, UTC).astimezone(TIMEZONE).strftime('%d.%m. %H:%M' if date else '%H:%M')


def duration(ms: int) -> str:
    minutes = max(0, (ms + 59999) // 60000)
    return f'{minutes // 60} h {minutes % 60:02d} min' if minutes >= 60 else f'{minutes} min'


def reveal_detail(carrier: Carrier, field: str, observed_ms: int, history: dict | None = None,
                  estimate: Estimate | None = None, *, stale: bool = False) -> str:
    if getattr(carrier, field) is not None:
        info = (history or {}).get(field, {})
        first, previous = info.get('first_seen'), info.get('last_unknown')
        if first is None:
            return 'Bereits bekannt'
        if previous is not None and previous < first:
            # Polling brackets the disclosure; it does not identify an exact second.
            return f'Reveal {clock(previous, date=True)}–{clock(first, date=True)}'
        return f'Erstmals erfasst {clock(first, date=True)}'
    if field == 'system':
        if observed_ms < carrier.spawn_ms:
            return f'Ab Spawn {clock(carrier.spawn_ms)} · in {duration(carrier.spawn_ms - observed_ms)}'
        return f'Ab Spawn {clock(carrier.spawn_ms)} · Meldung ausstehend'
    if estimate:
        deadline = carrier.spawn_ms + estimate.age_ms
        if stale:
            return f'Geschätzt ca. {clock(deadline)} · letzter Stand'
        if deadline <= observed_ms:
            return f'Schätzung {clock(deadline)} verstrichen · offen'
        return f'Geschätzt ~{duration(deadline-observed_ms)} · ca. {clock(deadline)}'
    return 'Lerne Reveal-Zeit · noch keine Messung'


def estimate_basis(carrier: Carrier, estimate: Estimate | None) -> str:
    if not estimate:
        return 'Bei Anschuss sofort bekannt'
    cohort = 'XC' if carrier.kind == 'boss' else 'SC'
    low, high = estimate.low_ms // 60000, (estimate.high_ms + 59999) // 60000
    uncertainty = ' · unsicher' if estimate.uncertain else ''
    return f'{cohort} · n={estimate.count} · {low}–{high} min ab Spawn{uncertainty}'


def departure_detail(carrier: Carrier, observed_ms: int, *, stale: bool = False) -> str:
    if carrier.departure_ms is None:
        return 'Abflugzeit unbekannt'
    if stale:
        return f'Abflug {clock(carrier.departure_ms)} · letzter Stand'
    if carrier.departure_ms <= observed_ms:
        return f'Abflug {clock(carrier.departure_ms)} · Bestätigung offen'
    return f'Abflug {clock(carrier.departure_ms)} · in {duration(carrier.departure_ms - observed_ms)}'
