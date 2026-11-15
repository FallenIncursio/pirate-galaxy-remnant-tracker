from __future__ import annotations

import hashlib
import json
import re
import ssl
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from .storage import Store


class DiscordError(RuntimeError):
    def __init__(self, status: int | None = None, code: int | None = None):
        super().__init__(f'Discord request failed (HTTP {status or "network"}, code {code or "unknown"})')
        self.status, self.code = status, code


def validate_url(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or parsed.hostname != 'discord.com' or parsed.port not in (None, 443)
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or not re.fullmatch(r'/api/webhooks/\d+/[A-Za-z0-9_-]+', parsed.path)):
        raise ValueError('Expected a Discord incoming webhook URL')
    return value.rstrip('/')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Publisher:
    def __init__(self, url: str, store: Store, *, opener=None, sleep=time.sleep):
        self.url = validate_url(url)
        self.target = hashlib.sha256(self.url.encode()).hexdigest()
        self.store = store
        self.opener = opener or urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()))
        self.sleep = sleep

    def request(self, method: str, suffix: str, data: dict | None = None) -> dict:
        encoded = json.dumps(data, ensure_ascii=False).encode() if data is not None else None
        for attempt in range(3):
            request = urllib.request.Request(self.url + suffix, data=encoded, method=method,
                       headers={'Content-Type': 'application/json', 'User-Agent': 'PirateGalaxyRemnants/0.1'})
            try:
                with self.opener.open(request, timeout=20) as response:
                    return json.loads(response.read(1000000) or b'{}')
            except urllib.error.HTTPError as error:
                try:
                    body = json.loads(error.read(20000))
                except (ValueError, OSError):
                    body = {}
                code = body.get('code')
                if error.code == 429 and attempt < 2:
                    try:
                        delay = float(body.get('retry_after', 5))
                    except (ValueError, TypeError):
                        delay = 5
                    if 0 <= delay <= 60:
                        self.sleep(max(delay, 0.1))
                        continue
                # A failed/ambiguous POST is not automatically replayed, avoiding duplicate cards.
                raise DiscordError(error.code, code if isinstance(code, int) else None) from None
            except (OSError, ValueError, urllib.error.URLError):
                raise DiscordError() from None
        raise DiscordError(429)

    def publish(self, payload: dict, now_ms: int) -> dict:
        message_id = self.store.message(self.target)
        method = 'PATCH' if message_id else 'POST'
        try:
            result = self.request(method, f'/messages/{message_id}' if message_id else '?wait=true', payload)
        except DiscordError as error:
            if method != 'PATCH' or error.status != 404 or error.code != 10008:
                raise
            result = self.request('POST', '?wait=true', payload)
            method = 'POST'
        message_id, channel_id = str(result.get('id', '')), str(result.get('channel_id', ''))
        if not message_id.isdigit() or not channel_id.isdigit():
            raise DiscordError()
        self.store.save_message(self.target, message_id, channel_id, now_ms)
        return {'method': method, 'message_id': message_id, 'channel_id': channel_id,
                'timestamp': result.get('timestamp'), 'edited_timestamp': result.get('edited_timestamp')}
