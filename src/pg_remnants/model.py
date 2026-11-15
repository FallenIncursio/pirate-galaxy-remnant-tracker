from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any


def text(value: Any, limit: int = 160, *, optional: bool = False) -> str | None:
    if value is None and optional:
        return None
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise ValueError('Invalid carrier string')
    if any(ord(c) < 32 for c in value):
        raise ValueError('Invalid carrier control character')
    return value


def integer(value: Any, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError('Invalid numeric carrier data')
    if not math.isfinite(value) or int(value) != value or not low <= value <= high:
        raise ValueError('Numeric carrier data outside range')
    return int(value)


@dataclass(frozen=True)
class Carrier:
    name: str
    spawn_ms: int
    kind: str
    system: str | None
    category: str | None
    planet: str | None
    hp: int | None
    departure_ms: int | None

    @property
    def key(self) -> str:
        return f'{self.name}|{self.spawn_ms}'

    def state(self) -> dict:
        # A counting-down timer is not a server-side event.
        return {k: v for k, v in asdict(self).items() if k != 'departure_ms'}


@dataclass(frozen=True)
class Snapshot:
    realm_id: int
    observed_ms: int
    carriers: tuple[Carrier, ...]

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict) -> Snapshot:
        return cls(raw['realm_id'], raw['observed_ms'], tuple(Carrier(**c) for c in raw['carriers']))

    @classmethod
    def from_event(cls, event: dict, expected_realm: int, now_ms: int) -> Snapshot:
        realm = integer(event.get('realm_id'), 1, 10000)
        observed = integer(event.get('observed_at_ms'), 1, now_ms + 30000)
        if realm != expected_realm or now_ms - observed > 60000:
            raise ValueError('Wrong realm or stale collector response')
        raw = event.get('carriers')
        if not isinstance(raw, list) or len(raw) > 100:
            raise ValueError('Invalid carrier list')
        carriers = []
        for c in raw:
            if not isinstance(c, dict):
                raise ValueError('Invalid carrier object')
            hp = c.get('HPStatus')
            hp = None if hp is None else integer(hp, 0, 100)
            remaining = c.get('timer_remaining')
            departure = None
            if remaining is not None and c.get('timer_hidden') is False:
                departure = observed + integer(remaining, 0, 31 * 86400000)
            carriers.append(Carrier(text(c.get('carrierName')), integer(c.get('spawnTime'), 1, now_ms + 300000),
                                    text(c.get('carrierType'), 50), text(c.get('starSystem'), optional=True),
                                    text(c.get('blueprintCategory'), optional=True), text(c.get('planet'), optional=True),
                                    hp, departure))
        if len({c.key for c in carriers}) != len(carriers):
            raise ValueError('Ambiguous duplicate carrier identity')
        return cls(realm, observed, tuple(sorted(carriers, key=lambda c: (c.system or '', c.spawn_ms, c.name))))


def changes(previous: Snapshot | None, current: Snapshot) -> list[str]:
    if previous is None or previous.realm_id != current.realm_id:
        return ['Erster erfasster Stand']
    before = {c.key: c for c in previous.carriers}
    after = {c.key: c for c in current.carriers}
    result = [f'Neu gelistet: {after[k].name}' for k in sorted(after.keys() - before.keys())]
    result += [f'Nicht mehr gelistet: {before[k].name}' for k in sorted(before.keys() - after.keys())]
    for key in sorted(before.keys() & after.keys()):
        old, new = before[key], after[key]
        if old.state() != new.state():
            labels = {'system': 'System', 'category': 'Beute', 'planet': 'Planet', 'hp': 'HP', 'kind': 'Typ'}
            fields = [label for field, label in labels.items() if getattr(old, field) != getattr(new, field)]
            result.append(f'Aktualisiert: {new.name} ({", ".join(fields)})')
    return result or ['Keine Änderungen seit dem letzten Abruf']
