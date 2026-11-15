import json
import os
from dataclasses import replace
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from pg_remnants.config import Config
from pg_remnants.discord import Publisher,DiscordError
from pg_remnants.service import run
from pg_remnants.storage import Store
from tests.test_service import FakeCollector


class MultipleTargetsTests(unittest.TestCase):
    def test_failure_isolated_and_distinct_message_ids_resume(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)
            cfg=Config(p,'Test',2,180,p/'cred',p/'manifest',p/'data',p/'start','Test',p/'sandbox','HOOK_A','Test',30,
                       webhook_environments=('HOOK_A','HOOK_B'))
            urls={'HOOK_A':'https://discord.com/api/webhooks/1/test-a','HOOK_B':'https://discord.com/api/webhooks/2/test-b'}
            healthy_sent=threading.Event(); calls=[]; fail_a=True
            def deliver(pub,payload,now_ms,*,image,message_id,persist):
                self.assertFalse(persist)
                is_a='/1/' in pub.url
                calls.append(('a' if is_a else 'b',message_id))
                if is_a and fail_a:
                    self.assertTrue(healthy_sent.wait(5),'A failure must not block the other channel')
                    raise DiscordError(503)
                if not is_a: healthy_sent.set()
                return {'message_id':'101' if is_a else '202','channel_id':'11' if is_a else '22',
                        'method':'PATCH' if message_id else 'POST','attachment_id':'303'}
            with patch.dict(os.environ,urls),patch('pg_remnants.service.Collector',FakeCollector),patch.object(Publisher,'publish',deliver):
                self.assertEqual(run(cfg,cycles=1),0)
                status=json.loads((cfg.data/'status.json').read_text())
                self.assertEqual(status['discord_targets']['HOOK_A']['state'],'error')
                self.assertEqual(status['discord_targets']['HOOK_B']['state'],'ok')
                self.assertIn(('b','202'),calls) # Final stopped card edits the successful target.
                fail_a=False;calls.clear()
                self.assertEqual(run(cfg,cycles=1),0)
            self.assertIn(('a',None),calls)
            self.assertIn(('a','101'),calls)
            self.assertTrue(all(mid=='202' for target,mid in calls if target=='b'))
            status=json.loads((cfg.data/'status.json').read_text())
            self.assertEqual(status['discord']['message_id'],'101')
            self.assertTrue(all(t['state']=='ok' for t in status['discord_targets'].values()))

    def test_duplicate_webhooks_are_published_once(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)
            cfg=Config(p,'Test',2,180,p/'cred',p/'manifest',p/'data',p/'start','Test',p/'sandbox','HOOK_A','Test',30,
                       webhook_environments=('HOOK_A','HOOK_B'))
            value='https://discord.com/api/webhooks/1/test-a'
            with patch.dict(os.environ,{'HOOK_A':value,'HOOK_B':value}),patch('pg_remnants.service.Collector',FakeCollector),\
                 patch.object(Publisher,'publish',return_value={'message_id':'1','channel_id':'2','method':'PATCH'}) as send:
                self.assertEqual(run(cfg,cycles=1),0)
            self.assertEqual(send.call_count,2) # One active and one stopped update, not two per channel alias.


if __name__=='__main__': unittest.main()
