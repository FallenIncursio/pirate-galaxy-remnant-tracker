import json
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from tests.helpers import event
from pg_remnants.config import Config
from pg_remnants.locking import single_instance
from pg_remnants.service import run


class FakeCollector:
    stopped = 0
    fresh_session = True
    fresh_graph = False
    def __init__(self, config):
        self.started = time.monotonic()
    def prepare(self): pass
    def start(self): pass
    def stop(self): type(self).stopped += 1
    def exit_code(self): return None
    def events(self):
        row = event(); row['observed_at_ms'] = int(time.time()*1000)
        row['fresh_session'],row['fresh_graph'] = self.fresh_session,self.fresh_graph
        row['carriers'][0]['spawnTime'] = row['observed_at_ms'] - 3600000
        return [row]


class ServiceTests(unittest.TestCase):
    def test_retained_session_requires_verified_graph(self):
        for verified in (True,False):
            with self.subTest(verified=verified),tempfile.TemporaryDirectory() as directory:
                p=Path(directory)
                cfg=Config(p,'Korell',2,180,p/'cred',p/'manifest',p/'data',p/'start','Test',p/'sandbox','UNUSED','Test',30)
                with patch('pg_remnants.service.Collector',FakeCollector), \
                     patch.object(FakeCollector,'fresh_session',False),patch.object(FakeCollector,'fresh_graph',verified):
                    if verified:
                        self.assertEqual(run(cfg,cycles=1,dry_run=True),0)
                    else:
                        with self.assertRaisesRegex(ValueError,'verified fresh data'):
                            run(cfg,cycles=1,dry_run=True)

    def test_bounded_dry_run_records_real_candidate_and_stops_child(self):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory)
            cfg = Config(p,'Korell',2,180,p/'cred',p/'manifest',p/'data',p/'start','Test',p/'sandbox','UNUSED','Test',30)
            FakeCollector.stopped = 0
            with patch('pg_remnants.service.Collector',FakeCollector):
                self.assertEqual(run(cfg,cycles=1,dry_run=True),0)
            self.assertGreater(FakeCollector.stopped,0)
            self.assertEqual(json.loads((cfg.data/'status.json').read_text())['state'],'stopped')
            self.assertTrue((cfg.data/'preview.json').is_file())

    def test_single_instance_prevents_duplicate_publishers(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'lock'
            with single_instance(path):
                with self.assertRaises(RuntimeError):
                    with single_instance(path):
                        self.fail('duplicate tracker started')
