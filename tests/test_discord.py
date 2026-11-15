import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path

from tests.helpers import NOW
from pg_remnants.discord import DiscordError, Publisher, validate_url
from pg_remnants.storage import Store

URL = 'https://discord.com/api/webhooks/0/example_token'


class Opener:
    def __init__(self, replies):
        self.replies, self.requests = list(replies), []
    def open(self, request, timeout):
        self.requests.append(request)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return io.BytesIO(json.dumps(reply).encode())


def failure(status, **body):
    return urllib.error.HTTPError(URL, status, 'not logged', {}, io.BytesIO(json.dumps(body).encode()))


class DiscordTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temporary.name) / 'history.sqlite3')
    def tearDown(self):
        self.store.close(); self.temporary.cleanup()

    def test_create_then_edit_same_message_across_publisher_restart(self):
        opener = Opener([{'id':'11','channel_id':'22'}, {'id':'11','channel_id':'22'}])
        first = Publisher(URL, self.store, opener=opener).publish({}, NOW)
        second = Publisher(URL, self.store, opener=opener).publish({}, NOW+180000)
        self.assertEqual([r.method for r in opener.requests], ['POST','PATCH'])
        self.assertEqual(first['message_id'], second['message_id'])
        self.assertTrue(opener.requests[0].full_url.endswith('?wait=true'))

    def test_deleted_message_is_recreated(self):
        opener = Opener([{'id':'11','channel_id':'22'}, failure(404,code=10008), {'id':'33','channel_id':'22'}])
        publisher = Publisher(URL, self.store, opener=opener)
        publisher.publish({}, NOW)
        self.assertEqual(publisher.publish({}, NOW+1)['message_id'], '33')
        self.assertEqual([r.method for r in opener.requests], ['POST','PATCH','POST'])

    def test_invalid_webhook_does_not_trigger_create(self):
        opener = Opener([{'id':'11','channel_id':'22'}, failure(404,code=10015)])
        publisher = Publisher(URL, self.store, opener=opener)
        publisher.publish({}, NOW)
        with self.assertRaises(DiscordError):
            publisher.publish({}, NOW+1)
        self.assertEqual(len(opener.requests), 2)

    def test_rate_limit_wait_is_honored(self):
        sleeps = []
        opener = Opener([failure(429,retry_after=0.25), {'id':'11','channel_id':'22'}])
        Publisher(URL, self.store, opener=opener, sleep=sleeps.append).publish({}, NOW)
        self.assertEqual(sleeps, [0.25])

    def test_network_error_does_not_leak_url_or_retry_post(self):
        opener = Opener([urllib.error.URLError(URL)])
        with self.assertRaises(DiscordError) as error:
            Publisher(URL, self.store, opener=opener).publish({}, NOW)
        self.assertNotIn('example_token', str(error.exception))
        self.assertEqual(len(opener.requests), 1)

    def test_unexpected_origin_or_query_is_rejected(self):
        for url in ('http://discord.com/api/webhooks/0/x', URL+'?x=y', URL.replace('discord.com','example.com'), URL.replace('discord.com','user@discord.com')):
            with self.subTest(url=url), self.assertRaises(ValueError):
                validate_url(url)

    def test_changed_webhook_does_not_reuse_old_message(self):
        opener = Opener([{'id':'11','channel_id':'22'}, {'id':'33','channel_id':'44'}])
        Publisher(URL, self.store, opener=opener).publish({}, NOW)
        Publisher(URL.replace('/0/', '/1/'), self.store, opener=opener).publish({}, NOW+1)
        self.assertEqual([r.method for r in opener.requests], ['POST','POST'])
