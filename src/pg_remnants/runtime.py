from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import time
from pathlib import Path

from .config import Config, credentials

SOURCE_ROOT = Path(__file__).resolve().parents[2]


def command(args, **kwargs):
    return subprocess.run([str(a) for a in args], capture_output=True, timeout=40,
                          creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), **kwargs)


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding='utf-8-sig'))


def atomic_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temporary, path)


def box_pids(config: Config) -> list[int]:
    result = command([config.sandbox_start, '/box:' + config.sandbox_box, '/listpids'])
    if result.returncode:
        raise RuntimeError('Cannot inspect dedicated Sandboxie box')
    raw = result.stdout.decode('utf-16le' if b'\0' in result.stdout else 'utf-8-sig')
    ids = [int(x) for x in raw.split()]
    if not ids or ids[0] != len(ids) - 1:
        raise RuntimeError('Unexpected Sandboxie process inventory')
    return ids[1:]


def check_box(config: Config) -> None:
    ini = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'Sandboxie.ini'
    raw = ini.read_bytes()
    content = raw.decode('utf-16' if raw.startswith((b'\xff\xfe', b'\xfe\xff')) else 'utf-8-sig')
    import re
    parts = re.split(r'^\[([^]\r\n]+)\]\s*$', content, flags=re.M)
    sections = {parts[i]: parts[i + 1] for i in range(1, len(parts) - 1, 2)}
    section = sections.get(config.sandbox_box, '')
    roots = re.findall(r'^FileRootPath=(.+)$', section, flags=re.M)
    if len(roots) != 1 or Path(roots[0].strip()).resolve() != config.sandbox_root:
        raise RuntimeError('Dedicated Sandboxie box is missing or has a different root')
    if not re.search(r'^Enabled=y\s*$', section, flags=re.M):
        raise RuntimeError('Dedicated Sandboxie box is not enabled')


def shadow(config: Config, path: Path) -> Path:
    profile = Path(os.environ['USERPROFILE'])
    if path.is_relative_to(profile):
        return config.sandbox_root / 'user/current' / path.relative_to(profile)
    return config.sandbox_root / 'drive' / path.drive.rstrip(':') / Path(*path.parts[1:])


class Collector:
    def __init__(self, config: Config):
        self.config = config
        self.run: Path | None = None
        self.output: Path | None = None
        self.offset = 0
        self.pending = b''
        self.started = 0.0
        self.classes = config.data / 'classes'
        self.process: subprocess.Popen | None = None

    def prepare(self) -> None:
        cfg = self.config
        if cfg.backend == 'sandboxie':
            if os.name != 'nt':
                raise RuntimeError('Sandboxie requires Windows; use the process backend on Linux')
            check_box(cfg)
        self.manifest = read_json(cfg.runtime_manifest)
        base = cfg.runtime_manifest.parent
        for relative, expected in self.manifest['hashes'].items():
            path = (base / relative).resolve()
            if not path.is_relative_to(base.resolve()) or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                raise RuntimeError('Runtime input changed; run setup and validate compatibility')
        self.java = base / self.manifest['java']
        if self.manifest.get('java_sha256') and hashlib.sha256(self.java.read_bytes()).hexdigest() != self.manifest['java_sha256']:
            raise RuntimeError('Java executable changed; update the verified runtime manifest')
        self.cp = os.pathsep.join(str(base / p) for p in self.manifest['classpath'])
        sources = [SOURCE_ROOT / 'collector/HeadlessRemnant.java', SOURCE_ROOT / 'collector/RemnantData.java']
        source_hash = hashlib.sha256(b''.join(s.read_bytes() for s in sources) + self.cp.encode()).hexdigest()
        stamp = self.classes / 'source.sha256'
        if not stamp.exists() or stamp.read_text() != source_hash:
            self.classes.mkdir(parents=True, exist_ok=True)
            result = command([self.manifest['javac'], '--release', '8', '-proc:none', '-encoding', 'UTF-8',
                              '-Xlint:-options', '-cp', self.cp, '-d', self.classes, *sources])
            if result.returncode:
                raise RuntimeError('Java collector compilation failed; check matching JDK and client inputs')
            stamp.write_text(source_hash)

    def start(self) -> None:
        cfg = self.config
        if self.run is not None:
            raise RuntimeError('Collector is already started')
        if cfg.backend == 'sandboxie' and box_pids(cfg):
            raise RuntimeError('Dedicated collector sandbox is already occupied')
        run = cfg.data / 'runs' / str(time.time_ns())
        for folder in ('', 'home', 'temp', 'appdata', 'localappdata', 'no-natives'):
            (run / folder).mkdir(parents=True, exist_ok=True, mode=0o700)
        (run / 'log4j2.xml').write_text('<Configuration status="OFF"><Loggers><Root level="OFF"/></Loggers></Configuration>')
        args = ['-XX:+DisableAttachMechanism', '-Xverify:all', '-Xms32m', '-Xmx256m', '-Djava.awt.headless=true',
                '-Duser.home=' + str(run / 'home'), '-Djava.io.tmpdir=' + str(run / 'temp'),
                '-Djava.library.path=' + str(run / 'no-natives'), '-Dlog4j1.compatibility=true',
                '-Dlog4j.configurationFile=' + str(run / 'log4j2.xml'),
                '-cp', str(self.classes) + os.pathsep + self.cp, 'HeadlessRemnant']
        atomic_json(run / 'launch.json', {'java': str(self.java), 'arguments': args})
        guest = SOURCE_ROOT / 'windows/collector-guest.ps1'
        user, password = credentials(cfg.credentials_file)
        env = {k: v for k, v in os.environ.items() if not k.startswith('DISCORD_WEBHOOK')}
        for name in cfg.webhook_names:
            env.pop(name, None)
        for k in ('JAVA_TOOL_OPTIONS', 'JDK_JAVA_OPTIONS', '_JAVA_OPTIONS', 'EXTRACT_NATIVES',
                  'PG_TEST_AWT_DRIVER', 'PG_TEST_DRIVER_DIR'):
            env.pop(k, None)
        if os.name != 'nt':
            # The original login helper reads Windows environment names even headless.
            # Supply this host's identity and private per-run directories on Unix.
            env.update(COMPUTERNAME=platform.node(), Processor_Identifier=platform.machine(),
                       Processor_Revision='', APPDATA=str(run / 'appdata'),
                       LOCALAPPDATA=str(run / 'localappdata'))
        env.update(PG_USERNAME=user, PG_PASSWORD=password, PG_REALM_ID=str(cfg.realm_id),
                   PG_SAMPLE_SECONDS=str(cfg.poll_seconds), PG_OUTPUT=str(run / 'events.jsonl'),
                   PG_STOP_FILE=str(run / 'stop.request'), PG_MAX_SAMPLES='0')
        if cfg.backend == 'sandboxie':
            # PowerShell Start-Process expects an already quoted argument string.
            atomic_json(run / 'launch.json', {'java': str(self.java), 'arguments': subprocess.list2cmdline(args)})
            powershell = Path(os.environ.get('WINDIR', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
            result = command([cfg.sandbox_start, '/box:' + cfg.sandbox_box, powershell, '-NoLogo', '-NoProfile',
                              '-ExecutionPolicy', 'Bypass', '-WindowStyle', 'Hidden', '-File', guest, '-RunDirectory', run],
                             env=env, cwd=run)
            if result.returncode:
                raise RuntimeError('Cannot launch collector in Sandboxie')
            self.output = shadow(cfg, run)
        else:
            self.process = subprocess.Popen([str(self.java), *args], cwd=run, env=env,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            self.output = run
            atomic_json(run / 'running.json', {'pid': self.process.pid, 'started_ms': int(time.time()*1000)})
        del env, user, password
        self.run = run
        self.offset, self.pending, self.started = 0, b'', time.monotonic()
        atomic_json(cfg.data / 'collector.json', {'run': str(run), 'output': str(self.output),
                    'backend': cfg.backend, 'box': cfg.sandbox_box if cfg.backend=='sandboxie' else None})

    def events(self) -> list[dict]:
        if self.output is None:
            return []
        path = self.output / 'events.jsonl'
        try:
            with path.open('rb') as handle:
                handle.seek(self.offset)
                chunk = handle.read(2_000_000)
                self.offset = handle.tell()
        except FileNotFoundError:
            return []
        lines = (self.pending + chunk).split(b'\n')
        self.pending = lines.pop()
        if len(self.pending) > 1_000_000:
            raise ValueError('Collector record exceeded limit')
        return [json.loads(line) for line in lines if line.strip()]

    def exit_code(self) -> int | None:
        if self.process is not None:
            return self.process.poll()
        try:
            return int(read_json(self.output / 'exit.json')['exit_code']) if self.output else None
        except FileNotFoundError:
            return None

    def stop(self) -> None:
        if self.run is None:
            return
        (self.run / 'stop.request').touch()
        if self.process is not None:
            try:
                self.process.wait(timeout=12)
            except subprocess.TimeoutExpired:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait(timeout=5)
            atomic_json(self.run / 'exit.json', {'pid': self.process.pid, 'exit_code': self.process.returncode})
            self.process = None
            self.run = None
            return
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline and box_pids(self.config):
            time.sleep(0.25)
        if box_pids(self.config):
            # Only the explicitly configured, dedicated collector box is terminated.
            check_box(self.config)
            result = command([self.config.sandbox_start, '/box:' + self.config.sandbox_box, '/terminate'])
            if result.returncode:
                raise RuntimeError('Collector sandbox did not stop')
        self.run = None
