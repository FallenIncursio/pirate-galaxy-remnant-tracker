from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Config:
    root: Path
    server: str
    realm_id: int
    poll_seconds: int
    credentials_file: Path
    runtime_manifest: Path
    data: Path
    sandbox_start: Path
    sandbox_box: str
    sandbox_root: Path
    webhook_environment: str
    username: str
    retention_days: int
    backend: str = 'sandboxie'
    webhook_environments: tuple[str, ...] = ()

    @property
    def webhook_names(self) -> tuple[str, ...]:
        return self.webhook_environments or (self.webhook_environment,)


def load(path: Path) -> Config:
    path = path.resolve()
    with path.open('rb') as handle:
        raw = tomllib.load(handle)
    root = path.parent
    def local(value: str) -> Path:
        p = Path(os.path.expandvars(value)).expanduser()
        return p.resolve() if p.is_absolute() else (root / p).resolve()
    tracker, runtime, discord = raw['tracker'], raw['runtime'], raw['discord']
    sandbox = raw.get('sandbox', {})
    names = discord.get('webhook_environments', [])
    if not isinstance(names, list) or any(not isinstance(n,str) for n in names):
        raise ValueError('webhook_environments must be a list of environment variable names')
    config = Config(root, str(tracker['server']), int(tracker['realm_id']),
                    int(tracker.get('poll_seconds', 180)), local(runtime['credentials_file']),
                    local(runtime.get('manifest', 'data/runtime/manifest.json')),
                    local(raw.get('paths', {}).get('data', 'data')),
                    local(sandbox.get('start', '%ProgramFiles%/Sandboxie-Plus/Start.exe')),
                    str(sandbox.get('box','PirateGalaxyRemnants')), local(sandbox.get('root','data/sandbox')),
                    str(discord.get('webhook_environment', 'DISCORD_WEBHOOK_URL')),
                    str(discord.get('username', 'Remnant Tracker')),
                    int(tracker.get('retention_days', 30)),
                    str(runtime.get('backend', 'sandboxie' if os.name == 'nt' else 'process')), tuple(names))
    if not 60 <= config.poll_seconds <= 3600 or config.realm_id <= 0:
        raise ValueError('Invalid realm or polling interval (60–3600 seconds)')
    if not 1 <= config.retention_days <= 365:
        raise ValueError('Invalid history retention')
    if not config.sandbox_box.replace('_', '').isalnum():
        raise ValueError('Invalid dedicated sandbox name')
    if config.backend not in ('sandboxie','process'):
        raise ValueError('runtime.backend must be sandboxie or process')
    if len(config.webhook_names) > 10 or len(set(config.webhook_names)) != len(config.webhook_names):
        raise ValueError('Use up to ten distinct webhook environment names')
    if any(not re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]*', name) for name in config.webhook_names):
        raise ValueError('Invalid webhook environment name')
    return config


def load_secrets(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, sep, value = line.partition('=')
        if not sep or not key.replace('_', '').isalnum():
            raise ValueError('Invalid secrets.env syntax')
        os.environ.setdefault(key, value.strip())


def credentials(path: Path) -> tuple[str, str]:
    fields = {}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        key, sep, value = line.partition(':')
        if sep and key.strip().lower() in ('name', 'pw'):
            fields[key.strip().lower()] = value.strip()
    if not fields.get('name') or not fields.get('pw'):
        raise ValueError('Credential file requires Name: and PW:')
    return fields['name'], fields['pw']
