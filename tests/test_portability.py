import importlib.util
import hashlib
import json
import os
import shutil
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile
import time
import unittest
from dataclasses import replace
from unittest.mock import patch

from tests.helpers import NOW
from pg_remnants.config import load, Config
from pg_remnants.runtime import Collector


class PortableTests(unittest.TestCase):
    def test_setup_is_relocatable_and_refuses_existing_installation(self):
        source=Path(__file__).resolve().parents[1]/'scripts/setup_runtime.py'
        spec=importlib.util.spec_from_file_location('setup_runtime',source)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);game=p/'client inputs';game.mkdir()
            jar=game/'PirateGalaxy-test.jar';jar.write_bytes(b'local test library')
            for name in ('log4j','mina'):
                (game/name).mkdir();(game/name/'dependency.jar').write_bytes(b'dependency')
            cred=p/'account.txt';cred.write_text('Name: test\nPW: test\n')
            config=p/'installation/config.toml'
            args=['setup_runtime.py','--backend','process','--game',str(game),'--credentials',str(cred),
                  '--java',sys.executable,'--javac',sys.executable,'--config',str(config)]
            def version(cmd,**kwargs):
                return subprocess.CompletedProcess(cmd,0,stdout='javac 21.0.1',stderr='openjdk version "21.0.1"')
            with patch.object(module,'TESTED_JAR',hashlib.sha256(jar.read_bytes()).hexdigest()),\
                 patch.object(module.subprocess,'run',side_effect=version),patch.object(sys,'argv',args):
                original_umask=os.umask(0o077) if os.name!='nt' else None
                try:
                    module.main()
                    c=load(config)
                    self.assertEqual(c.backend,'process')
                    self.assertEqual(c.credentials_file,cred.resolve())
                    manifest=json.loads(c.runtime_manifest.read_text())
                    self.assertEqual(len(manifest['classpath']),3)
                    self.assertEqual(Path(manifest['java']),Path(sys.executable).resolve())
                    with self.assertRaises(SystemExit): module.main()
                finally:
                    if original_umask is not None: os.umask(original_umask)

    def test_relative_configuration_and_multiple_environment_names(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'config.toml'
            p.write_text('''[tracker]
server="Example"
realm_id=2
[runtime]
backend="process"
credentials_file="private/account.txt"
[discord]
webhook_environments=["HOOK_A","HOOK_B"]
''')
            c=load(p)
            self.assertEqual(c.backend,'process')
            self.assertEqual(c.webhook_names,('HOOK_A','HOOK_B'))
            self.assertEqual(c.credentials_file,(p.parent/'private/account.txt').resolve())
            self.assertEqual(c.data,(p.parent/'data').resolve())
            for value in ('["BAD NAME"]','["DUP","DUP"]','"HOOK_A"'):
                p.write_text(p.read_text().replace('["HOOK_A","HOOK_B"]',value))
                with self.assertRaises(ValueError): load(p)
                p.write_text(p.read_text().replace(value,'["HOOK_A","HOOK_B"]'))

    def test_direct_child_receives_only_game_credentials_and_stops(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder);cred=p/'account.txt';cred.write_text('Name: test-user\nPW: test-password\n')
            cfg=Config(p,'Test',2,180,cred,p/'manifest',p/'data',p/'unused','Test',p/'sandbox','HOOK_A','Test',30,
                       backend='process',webhook_environments=('HOOK_A','HOOK_B'))
            collector=Collector(cfg);collector.java=Path(sys.executable);collector.cp='test-classpath'
            original=subprocess.Popen; captured={}
            script='import os,time; from pathlib import Path; p=Path(os.environ["PG_STOP_FILE"]);\nwhile not p.exists(): time.sleep(0.02)'
            def spawn(args,**kwargs):
                captured.update(args=args,env=dict(kwargs['env']))
                return original([sys.executable,'-c',script],**kwargs)
            with patch.dict(os.environ,{'HOOK_A':'secret-a','HOOK_B':'secret-b','DISCORD_WEBHOOK_EXTRA':'secret-c',
                                        'JAVA_TOOL_OPTIONS':'unexpected'}),patch('pg_remnants.runtime.subprocess.Popen',side_effect=spawn):
                collector.start()
            self.assertIsNone(collector.exit_code())
            self.assertIn('-Djava.awt.headless=true',captured['args'])
            self.assertEqual(captured['env']['PG_USERNAME'],'test-user')
            self.assertEqual(captured['env']['PG_PASSWORD'],'test-password')
            for secret in ('HOOK_A','HOOK_B','DISCORD_WEBHOOK_EXTRA','JAVA_TOOL_OPTIONS'):
                self.assertNotIn(secret,captured['env'])
            self.assertNotIn('test-password',' '.join(map(str,captured['args'])))
            run=collector.run;child=collector.process
            collector.stop()
            self.assertEqual(child.poll(),0)
            self.assertEqual(json.loads((run/'exit.json').read_text())['exit_code'],0)
            self.assertIsNone(collector.run)

    def test_systemd_quotes_special_paths_without_shell_or_venv_resolution(self):
        path=Path(__file__).resolve().parents[1]/'scripts/install_systemd.py'
        spec=importlib.util.spec_from_file_location('install_systemd',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        config=PurePosixPath('/srv/my tracker/100%/$private/config.toml')
        unit=module.unit_text(config,PurePosixPath('/srv/my tracker/.venv/bin/python'))
        self.assertIn('100%%/$$private/config.toml',unit)
        self.assertIn('"/srv/my tracker/.venv/bin/python" -m pg_remnants',unit)
        self.assertIn('KillMode=mixed',unit)
        self.assertIn('WantedBy=default.target',unit)
        self.assertNotIn('password',unit.lower())
        with self.assertRaises(ValueError): module.unit_quote('/tmp/a\nExecStart=bad')

    @unittest.skipUnless(sys.platform.startswith('linux') and shutil.which('systemd-analyze'), 'Requires systemd parser')
    def test_generated_service_is_accepted_by_systemd(self):
        path=Path(__file__).resolve().parents[1]/'scripts/install_systemd.py'
        spec=importlib.util.spec_from_file_location('install_systemd',path)
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory(prefix='remnant service ') as folder:
            unit=Path(folder)/'remnant-parser-check.service'
            unit.write_text(module.unit_text(Path(folder)/'100%/$private/config.toml',Path(sys.executable)))
            result=subprocess.run(['systemd-analyze','verify',str(unit)],capture_output=True,text=True,timeout=30)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)


if __name__=='__main__': unittest.main()
