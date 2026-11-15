from __future__ import annotations

import hashlib
import json
import re
import ssl
import time
import urllib.error
import urllib.request
import uuid
from urllib.parse import urlsplit

from .storage import Store

_STORED_MESSAGE = object()


class DiscordError(RuntimeError):
    def __init__(self, status: int | None = None, code: int | None = None):
        super().__init__(f'Discord request failed (HTTP {status or "network"}, code {code or "unknown"})')
        self.status, self.code = status, code


def validate_url(value: str) -> str:
    parsed = urlsplit(value)
    if (parsed.scheme != 'https' or parsed.hostname != 'discord.com' or parsed.port not in (None, 443)
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or not re.fullmatch(r'/api/(?:v10/)?webhooks/\d+/[A-Za-z0-9_-]+', parsed.path)):
        raise ValueError('Expected a Discord incoming webhook URL')
    return value.rstrip('/').replace('/api/v10/webhooks/', '/api/webhooks/')


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class Publisher:
    def __init__(self, url: str, store: Store, *, opener=None, sleep=time.sleep):
        canonical = validate_url(url)
        self.url = canonical.replace('/api/webhooks/', '/api/v10/webhooks/')
        self.target = hashlib.sha256(canonical.encode()).hexdigest()
        self.store = store
        self.opener = opener or urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=ssl.create_default_context()))
        self.sleep = sleep

    def request(self, method: str, suffix: str, data: dict | None = None, *, image: bytes | None = None) -> dict:
        encoded = json.dumps(data, ensure_ascii=False).encode() if data is not None else None
        content_type = 'application/json'
        if image is not None:
            if not image.startswith(b'\x89PNG\r\n\x1a\n') or len(image) > 8_000_000:
                raise ValueError('Expected a PNG status card under 8 MB')
            filename = data['attachments'][0]['filename']
            if not re.fullmatch(r'remnants-\d+\.png', filename):
                raise ValueError('Invalid status card filename')
            boundary = 'PGRemnants' + uuid.uuid4().hex
            content_type = 'multipart/form-data; boundary=' + boundary
            encoded = (f'--{boundary}\r\nContent-Disposition: form-data; name="payload_json"\r\n'
                       'Content-Type: application/json\r\n\r\n').encode() + encoded + (
                       f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="files[0]"; filename="{filename}"\r\n'
                       'Content-Type: image/png\r\n\r\n').encode() + image + f'\r\n--{boundary}--\r\n'.encode()
        for attempt in range(3):
            request = urllib.request.Request(self.url + suffix, data=encoded, method=method,
                       headers={'Content-Type': content_type, 'User-Agent': 'PirateGalaxyRemnants/0.2'})
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

    def publish(self, payload: dict, now_ms: int, *, image: bytes | None = None,
                message_id=_STORED_MESSAGE, persist: bool = True) -> dict:
        if message_id is _STORED_MESSAGE:
            message_id = self.store.message(self.target)
        method = 'PATCH' if message_id else 'POST'
        try:
            result = self.request(method, f'/messages/{message_id}' if message_id else '?wait=true', payload, image=image)
        except DiscordError as error:
            if method != 'PATCH' or error.status != 404 or error.code != 10008:
                raise
            result = self.request('POST', '?wait=true', payload, image=image)
            method = 'POST'
        message_id, channel_id = str(result.get('id', '')), str(result.get('channel_id', ''))
        if not message_id.isdigit() or not channel_id.isdigit():
            raise DiscordError()
        attachments = result.get('attachments', [])
        image_id = None
        if image is not None:
            filename = payload['attachments'][0]['filename']
            def confirmed_image(response):
                for attachment in response.get('attachments', []):
                    if attachment.get('filename') == filename:
                        return str(attachment.get('id', ''))
                # Discord can consume an uploaded file into the embed, leaving attachments empty.
                for embed in response.get('embeds', []):
                    uri = urlsplit(embed.get('image', {}).get('url', ''))
                    parts = uri.path.split('/')
                    if uri.hostname in ('cdn.discordapp.com', 'media.discordapp.net') and len(parts) >= 3 and parts[-1] == filename:
                        return parts[-2]
                return None
            image_id = confirmed_image(result)
            if not image_id:
                image_id = confirmed_image(self.request('GET', f'/messages/{message_id}'))
            if not image_id or not image_id.isdigit():
                raise DiscordError(200)
        if persist:
            self.store.save_message(self.target, message_id, channel_id, now_ms)
        return {'method': method, 'message_id': message_id, 'channel_id': channel_id,
                'timestamp': result.get('timestamp'), 'edited_timestamp': result.get('edited_timestamp'),
                'attachment_id': image_id}
