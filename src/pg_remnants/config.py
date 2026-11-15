from __future__ import annotations

import os
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


def load(path: Path) -> Config:
    path = path.resolve()
    with path.open('rb') as handle:
        raw = tomllib.load(handle)
    root = path.parent
    def local(value: str) -> Path:
        p = Path(os.path.expandvars(value)).expanduser()
        return p.resolve() if p.is_absolute() else (root / p).resolve()
    tracker, runtime, discord = raw['tracker'], raw['runtime'], raw['discord']
    sandbox = raw['sandbox']
    config = Config(root, str(tracker['server']), int(tracker['realm_id']),
                    int(tracker.get('poll_seconds', 180)), local(runtime['credentials_file']),
                    local(runtime.get('manifest', 'data/runtime/manifest.json')),
                    local(raw.get('paths', {}).get('data', 'data')),
                    local(sandbox['start']), str(sandbox['box']), local(sandbox['root']),
                    str(discord.get('webhook_environment', 'DISCORD_WEBHOOK_URL')),
                    str(discord.get('username', 'Remnant Tracker')),
                    int(tracker.get('retention_days', 30)))
    if not 60 <= config.poll_seconds <= 3600 or config.realm_id <= 0:
        raise ValueError('Invalid realm or polling interval (60–3600 seconds)')
    if not 1 <= config.retention_days <= 365:
        raise ValueError('Invalid history retention')
    if not config.sandbox_box.replace('_', '').isalnum():
        raise ValueError('Invalid dedicated sandbox name')
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
