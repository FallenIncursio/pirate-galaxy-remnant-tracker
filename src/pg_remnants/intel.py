"""Display facts and observation windows; never infer an unreported reveal deadline."""
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from .model import Carrier

TIMEZONE = ZoneInfo('Europe/Berlin')


def clock(ms: int, *, date: bool = False) -> str:
    return datetime.fromtimestamp(ms / 1000, UTC).astimezone(TIMEZONE).strftime('%d.%m. %H:%M' if date else '%H:%M')


def duration(ms: int) -> str:
    minutes = max(0, (ms + 59999) // 60000)
    return f'{minutes // 60} h {minutes % 60:02d} min' if minutes >= 60 else f'{minutes} min'


def reveal_detail(carrier: Carrier, field: str, observed_ms: int, history: dict | None = None) -> str:
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
    return 'Zeit offen · bei Anschuss sofort'


def departure_detail(carrier: Carrier, observed_ms: int, *, stale: bool = False) -> str:
    if carrier.departure_ms is None:
        return 'Abflugzeit unbekannt'
    if stale:
        return f'Abflug {clock(carrier.departure_ms)} · letzter Stand'
    if carrier.departure_ms <= observed_ms:
        return f'Abflug {clock(carrier.departure_ms)} · Bestätigung offen'
    return f'Abflug {clock(carrier.departure_ms)} · in {duration(carrier.departure_ms - observed_ms)}'
