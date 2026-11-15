import io
import json
import sqlite3
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

from PIL import Image
from tests.helpers import NOW, event
from pg_remnants.card import payload
from pg_remnants.intel import clock, departure_detail, reveal_detail
from pg_remnants.model import Snapshot
from pg_remnants.render import render
from pg_remnants.storage import Store


class IntelTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = Snapshot.from_event(event(), 2, NOW)
        self.carrier = self.snapshot.carriers[0]

    def test_unknown_reveals_have_no_fabricated_countdown(self):
        carrier = replace(self.carrier, category=None, planet=None, system=None)
        for field in ('category','planet'):
            self.assertEqual(reveal_detail(carrier,field,NOW), 'Zeit offen · bei Anschuss sofort')
        self.assertIn('Meldung ausstehend',reveal_detail(carrier,'system',NOW))
        future = replace(carrier,spawn_ms=NOW+60000)
        self.assertIn('in 1 min',reveal_detail(future,'system',NOW))

    def test_poll_window_is_distinguished_from_already_known(self):
        carrier = replace(self.carrier, planet='mizar2planet')
        known = {'planet': {'first_seen':NOW, 'last_unknown':None}}
        self.assertTrue(reveal_detail(carrier,'planet',NOW,known).startswith('Erstmals erfasst'))
        known['planet']['last_unknown'] = NOW-180000
        self.assertTrue(reveal_detail(carrier,'planet',NOW,known).startswith('Reveal '))
        self.assertIn('–',reveal_detail(carrier,'planet',NOW,known))

    def test_departure_expiry_is_not_a_claim_of_disappearance(self):
        carrier=replace(self.carrier,departure_ms=NOW-1000)
        self.assertIn('Bestätigung offen',departure_detail(carrier,NOW))
        self.assertIn('letzter Stand',departure_detail(carrier,NOW,stale=True))
        self.assertNotIn('in ',departure_detail(carrier,NOW,stale=True))

    def test_berlin_clock_observes_summer_and_winter_time(self):
        for month,hour in ((1,'13:00'),(7,'14:00')):
            stamp=int(datetime(2026,month,1,12,tzinfo=UTC).timestamp()*1000)
            self.assertEqual(clock(stamp),hour)

    def test_backfill_and_restart_preserve_reveal_observation(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/'history.sqlite3'
            unknown=replace(self.snapshot,carriers=(replace(self.carrier,planet=None),))
            known=replace(unknown,observed_ms=NOW+180000,carriers=(replace(unknown.carriers[0],planet='mizar2planet'),))
            # Legacy history has no intel_seen table.
            db=sqlite3.connect(path)
            db.execute('CREATE TABLE snapshots(realm INTEGER, observed INTEGER, payload TEXT, changes TEXT, PRIMARY KEY(realm,observed))')
            for s in (unknown,known):
                db.execute('INSERT INTO snapshots VALUES (?,?,?,?)',(2,s.observed_ms,json.dumps(s.to_dict()),'[]'))
            db.commit();db.close()
            store=Store(path)
            info=store.intel_history(known)[self.carrier.key]['planet']
            self.assertEqual(info,{'first_seen':NOW+180000,'last_unknown':NOW})
            store.close()
            store=Store(path)
            store.record(replace(known,observed_ms=NOW+360000),30)
            self.assertEqual(store.intel_history(known)[self.carrier.key]['planet'],info)
            other=replace(known,realm_id=3)
            self.assertEqual(store.intel_history(other)[self.carrier.key],{})
            store.close()

    def test_legacy_cached_unknown_is_not_used_as_reveal_lower_bound(self):
        with tempfile.TemporaryDirectory() as temp:
            store=Store(Path(temp)/'history.sqlite3')
            old=replace(self.snapshot,fresh_session=False,carriers=(replace(self.carrier,planet=None),))
            store.record(old,30)
            current=replace(old,observed_ms=NOW+180000,fresh_session=True,carriers=(replace(self.carrier,planet='mizar2planet'),))
            store.record(current,30)
            info=store.intel_history(current)[self.carrier.key]['planet']
            self.assertIsNone(info['last_unknown'])
            self.assertEqual(info['first_seen'],NOW+180000)
            store.close()

    def test_png_renders_unknown_zero_boss_and_stale_states(self):
        for hp,boss,problem in ((None,False,None),(0,True,None),(100,False,'Tracker gestoppt')):
            carrier=replace(self.carrier,hp=hp,kind='boss' if boss else 'normal')
            snapshot=replace(self.snapshot,carriers=(carrier,))
            png=render(snapshot,server='Korell',poll_seconds=180,now_ms=NOW,problem=problem)
            with Image.open(io.BytesIO(png)) as image:
                self.assertEqual(image.format,'PNG')
                self.assertEqual(image.width,1200)
                self.assertEqual(image.mode,'RGB')
            self.assertLess(len(png),8_000_000)

    def test_large_board_and_empty_board_are_bounded(self):
        huge=replace(self.snapshot,carriers=tuple(replace(self.carrier,name='X'*160) for _ in range(100)))
        for snapshot in (None,replace(self.snapshot,carriers=()),huge):
            png=render(snapshot,server='Korell',poll_seconds=180,now_ms=NOW)
            with Image.open(io.BytesIO(png)) as image:
                self.assertLess(image.height,3100)
            data=payload(snapshot,server='Korell',username='Test',poll_seconds=180,now_ms=NOW)
            self.assertLessEqual(len(data['attachments'][0]['description']),1024)
