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
        ''')

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
            self.db.execute('DELETE FROM snapshots WHERE observed < ?', (snapshot.observed_ms - retention_days * 86400000,))
        return delta

    def message(self, target: str) -> str | None:
        row = self.db.execute('SELECT message_id FROM publisher WHERE target=?', (target,)).fetchone()
        return row[0] if row else None

    def save_message(self, target: str, message_id: str, channel_id: str, published_ms: int) -> None:
        with self.db:
            self.db.execute('INSERT OR REPLACE INTO publisher VALUES (?,?,?,?)', (target, message_id, channel_id, published_ms))

    def close(self) -> None:
        self.db.close()
