import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from tests.helpers import NOW, event
from pg_remnants.model import Snapshot, changes
from pg_remnants.storage import Store
from pg_remnants.card import payload


class ModelTests(unittest.TestCase):
    def snapshot(self, raw=None):
        return Snapshot.from_event(raw or event(), 2, NOW)

    def test_unknown_hp_differs_from_zero(self):
        self.assertIsNone(self.snapshot().carriers[0].hp)
        raw = event(); raw['carriers'][0]['HPStatus'] = 0
        self.assertEqual(self.snapshot(raw).carriers[0].hp, 0)

    def test_rejects_invalid_hp_and_booleans(self):
        for value in (-1, 101, True, '99', float('nan')):
            raw = event(); raw['carriers'][0]['HPStatus'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.snapshot(raw)

    def test_wrong_realm_and_old_observation_are_rejected(self):
        for field, value in [('realm_id', 5), ('observed_at_ms', NOW - 61000), ('observed_at_ms', NOW + 31000)]:
            raw = event(); raw[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                self.snapshot(raw)

    def test_duplicate_identity_is_rejected(self):
        raw = event(); raw['carriers'] *= 2
        with self.assertRaises(ValueError):
            self.snapshot(raw)

    def test_unknown_and_hidden_timers_do_not_invent_departure(self):
        for modifications in ({'timer_hidden': True}, {'timer_remaining': None}, {'timer_hidden': None}):
            raw = event(); raw['carriers'][0].update(modifications)
            self.assertIsNone(self.snapshot(raw).carriers[0].departure_ms)

    def test_timer_is_absolute_but_not_an_event(self):
        first = self.snapshot()
        self.assertEqual(first.carriers[0].departure_ms, NOW + 600000)
        second = replace(first, observed_ms=NOW+180000, carriers=(replace(first.carriers[0], departure_ms=NOW+600050),))
        self.assertEqual(changes(first, second), ['Keine Änderungen seit dem letzten Abruf'])

    def test_missing_carrier_is_not_called_destroyed(self):
        empty = replace(self.snapshot(), observed_ms=NOW+1, carriers=())
        self.assertEqual(changes(self.snapshot(), empty), ['Nicht mehr gelistet: SC-Example'])

    def test_known_hp_change_is_reported(self):
        first = self.snapshot()
        second = replace(first, carriers=(replace(first.carriers[0], hp=80),))
        self.assertIn('(HP)', changes(first, second)[0])

    def test_safe_discord_card_preserves_unknown_and_disables_mentions(self):
        snap = self.snapshot()
        snap = replace(snap, carriers=(replace(snap.carriers[0], name='@everyone *test*'),))
        card = payload(snap, server='Korell', username='Test', poll_seconds=180, now_ms=NOW)
        self.assertEqual(card['allowed_mentions'], {'parse': []})
        field = card['embeds'][0]['fields'][0]
        self.assertNotIn('@everyone', field['name'])
        self.assertIn('HP: **unbekannt**', field['value'])
        self.assertIn('alle 3 Minuten', card['embeds'][0]['description'])

    def test_stale_card_does_not_claim_live_timer(self):
        card = payload(self.snapshot(), server='Korell', username='Test', poll_seconds=180, now_ms=NOW+999,
                       problem='Verbindung unterbrochen')
        self.assertIn('(letzter Stand)', card['embeds'][0]['fields'][0]['value'])
        self.assertIn('Datenstand:', card['embeds'][0]['description'])

    def test_large_snapshot_respects_discord_budget(self):
        snap = self.snapshot()
        snap = replace(snap, carriers=tuple(replace(snap.carriers[0], name='X'*150+str(i), planet='P'*150, category='C'*150) for i in range(100)))
        embed = payload(snap, server='Korell', username='Test', poll_seconds=180, now_ms=NOW, delta=['x'*1000]*30)['embeds'][0]
        size = len(embed['title']) + len(embed['description']) + len(embed['footer']['text'])
        size += sum(len(f['name'])+len(f['value']) for f in embed['fields'])
        self.assertLessEqual(size, 6000)
        self.assertLessEqual(len(embed['fields']), 25)


class HistoryTests(unittest.TestCase):
    def test_continuity_after_restart_and_monotonic_observations(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'history.sqlite3'
            snapshot = Snapshot.from_event(event(), 2, NOW)
            store = Store(path); store.record(snapshot, 30); store.close()
            store = Store(path)
            self.assertEqual(store.latest(2), snapshot)
            with self.assertRaises(ValueError):
                store.record(snapshot, 30)
            self.assertIsNone(store.latest(5))
            store.close()

    def test_empty_confirmed_snapshot_records_disappearance(self):
        with tempfile.TemporaryDirectory() as directory:
            store = Store(Path(directory) / 'history.sqlite3')
            snapshot = Snapshot.from_event(event(), 2, NOW)
            store.record(snapshot, 30)
            result = store.record(replace(snapshot, observed_ms=NOW+180000, carriers=()), 30)
            self.assertIn('Nicht mehr gelistet', result[0])
            store.close()
