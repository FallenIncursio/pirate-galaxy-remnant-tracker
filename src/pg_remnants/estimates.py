"""Empirical reveal ages, using only bracketed observations without combat evidence."""
from collections import defaultdict
from dataclasses import dataclass
from statistics import median

from .model import Snapshot

MINUTE = 60000


@dataclass(frozen=True)
class Estimate:
    count: int
    age_ms: int
    low_ms: int
    high_ms: int

    @property
    def uncertain(self) -> bool:
        return self.count < 5 or self.high_ms - self.low_ms > 10 * MINUTE


class RevealModel:
    def __init__(self, poll_seconds: int = 180):
        self.max_gap = (2 * poll_seconds + 30) * 1000
        self.previous: dict[int, Snapshot] = {}
        self.seen = {}
        self.combat = {}
        self.windows = defaultdict(list)

    def observe(self, current: Snapshot) -> None:
        previous = self.previous.get(current.realm_id)
        if previous and current.observed_ms <= previous.observed_ms:
            raise ValueError('Reveal history must advance within each realm')
        before = {c.key: c for c in previous.carriers} if previous else {}
        bracketed = (previous is not None and previous.verified_fresh and current.verified_fresh
                     and current.observed_ms - previous.observed_ms <= self.max_gap)
        for c in current.carriers:
            identity = (current.realm_id, c.key)
            # Even 100% HP can mean a hit followed by repair; don't learn from it.
            if c.hp is not None or c.departure_ms is not None:
                self.combat[identity] = current.observed_ms
            elif identity in self.combat:
                self.combat[identity] = current.observed_ms
            old = before.get(c.key)
            for field in ('category', 'planet'):
                key = (*identity, field)
                if getattr(c, field) is None:
                    continue
                if (key not in self.seen and bracketed and old is not None
                        and old.kind == c.kind and old.spawn_ms == c.spawn_ms
                        and getattr(old, field) is None and identity not in self.combat
                        and previous.observed_ms >= c.spawn_ms):
                    self.windows[(current.realm_id, c.kind, field)].append(
                        (current.observed_ms, previous.observed_ms-c.spawn_ms, current.observed_ms-c.spawn_ms))
                # First seen already known is censored, not a measured reveal age.
                self.seen[key] = current.observed_ms
        self.previous[current.realm_id] = current

    def prune(self, cutoff: int) -> None:
        self.seen = {key: stamp for key, stamp in self.seen.items() if stamp >= cutoff}
        self.combat = {key: stamp for key, stamp in self.combat.items() if stamp >= cutoff}
        self.windows = defaultdict(list, {key: [s for s in samples if s[0] >= cutoff]
                                         for key, samples in self.windows.items()})

    def estimates(self, realm: int, cutoff: int = 0) -> dict:
        result = {}
        for (sample_realm, kind, field), samples in self.windows.items():
            if sample_realm != realm:
                continue
            samples = [s for s in samples if s[0] >= cutoff]
            if samples:
                result[(kind, field)] = Estimate(
                    len(samples), round(median((low+high)/2 for _, low, high in samples)),
                    min(low for _, low, _ in samples), max(high for _, _, high in samples))
        return result
