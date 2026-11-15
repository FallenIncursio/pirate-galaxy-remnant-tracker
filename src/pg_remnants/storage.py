from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from .model import Snapshot, changes


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS snapshots (
                realm INTEGER NOT NULL, observed INTEGER NOT NULL, payload TEXT NOT NULL,
                changes TEXT NOT NULL, PRIMARY KEY(realm, observed));
            CREATE TABLE IF NOT EXISTS publisher (
                target TEXT PRIMARY KEY, message_id TEXT NOT NULL, channel_id TEXT,
                published_ms INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS intel_seen (
                realm INTEGER NOT NULL, carrier TEXT NOT NULL, field TEXT NOT NULL,
                first_seen INTEGER, last_unknown INTEGER, last_observed INTEGER NOT NULL,
                PRIMARY KEY(realm, carrier, field));
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        ''')
        marker = self.db.execute("SELECT value FROM metadata WHERE key='intel_history_v2'").fetchone()
        cutoff = int(marker[0]) if marker and marker[0].isdigit() else 0
        with self.db:
            if not marker:
                self.db.execute('DELETE FROM intel_seen')
            for row in self.db.execute('SELECT payload FROM snapshots WHERE observed>? ORDER BY observed', (cutoff,)):
                self._observe_intel(Snapshot.from_dict(json.loads(row[0])))

    def _observe_intel(self, snapshot: Snapshot) -> None:
        for carrier in snapshot.carriers:
            for field in ('system', 'category', 'planet'):
                known = getattr(carrier, field) is not None
                self.db.execute('''INSERT INTO intel_seen VALUES (?,?,?,?,?,?)
                    ON CONFLICT(realm,carrier,field) DO UPDATE SET
                        first_seen=COALESCE(intel_seen.first_seen,excluded.first_seen),
                        last_unknown=CASE WHEN intel_seen.first_seen IS NULL
                            THEN COALESCE(excluded.last_unknown,intel_seen.last_unknown)
                            ELSE intel_seen.last_unknown END,
                        last_observed=excluded.last_observed''',
                    (snapshot.realm_id, carrier.key, field, snapshot.observed_ms if known else None,
                     snapshot.observed_ms if not known and snapshot.fresh_session else None, snapshot.observed_ms))
        self.db.execute("INSERT OR REPLACE INTO metadata VALUES ('intel_history_v2',?)", (str(snapshot.observed_ms),))

    def intel_history(self, snapshot: Snapshot) -> dict:
        result = {}
        for carrier in snapshot.carriers:
            rows = self.db.execute('SELECT field,first_seen,last_unknown FROM intel_seen WHERE realm=? AND carrier=?',
                                   (snapshot.realm_id, carrier.key))
            result[carrier.key] = {field: {'first_seen': first, 'last_unknown': unknown}
                                   for field, first, unknown in rows}
        return result

    def latest(self, realm: int) -> Snapshot | None:
        row = self.db.execute('SELECT payload FROM snapshots WHERE realm=? ORDER BY observed DESC LIMIT 1', (realm,)).fetchone()
        return Snapshot.from_dict(json.loads(row[0])) if row else None

    def record(self, snapshot: Snapshot, retention_days: int) -> list[str]:
        previous = self.latest(snapshot.realm_id)
        if previous and snapshot.observed_ms <= previous.observed_ms:
            raise ValueError('Snapshot time did not advance')
        delta = changes(previous, snapshot)
        with self.db:
            self.db.execute('INSERT INTO snapshots VALUES (?,?,?,?)', (snapshot.realm_id, snapshot.observed_ms,
                            json.dumps(snapshot.to_dict(), ensure_ascii=False), json.dumps(delta, ensure_ascii=False)))
            self._observe_intel(snapshot)
            self.db.execute('DELETE FROM snapshots WHERE observed < ?', (snapshot.observed_ms - retention_days * 86400000,))
            self.db.execute('DELETE FROM intel_seen WHERE last_observed < ?', (snapshot.observed_ms - retention_days * 86400000,))
        return delta

    def message(self, target: str) -> str | None:
        row = self.db.execute('SELECT message_id FROM publisher WHERE target=?', (target,)).fetchone()
        return row[0] if row else None

    def save_message(self, target: str, message_id: str, channel_id: str, published_ms: int) -> None:
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO publisher VALUES (?,?,?,?)', (target, message_id, channel_id, published_ms))

    def close(self) -> None:
        self.db.close()
