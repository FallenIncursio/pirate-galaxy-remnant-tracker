import io
import json
import tempfile
import unittest
import urllib.error
from email import policy
from email.parser import BytesParser
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

    def test_api_v10_preserves_existing_unversioned_message_identity(self):
        opener=Opener([{'id':'11','channel_id':'22'}, {'id':'11','channel_id':'22'}])
        Publisher(URL,self.store,opener=opener).publish({},NOW)
        Publisher(URL.replace('/api/','/api/v10/'),self.store,opener=opener).publish({},NOW+1)
        self.assertEqual([r.method for r in opener.requests],['POST','PATCH'])
        self.assertTrue(all('/api/v10/webhooks/' in r.full_url for r in opener.requests))

    def test_png_replaces_attachment_on_same_message_and_preserves_binary(self):
        from pg_remnants.card import payload
        png=b'\x89PNG\r\n\x1a\n\x00\xfftest'
        replies=[{'id':'11','channel_id':'22','attachments':[{'id':str(i),'filename':f'remnants-{NOW+i}.png'}]} for i in (0,1)]
        opener=Opener(replies)
        publisher=Publisher(URL,self.store,opener=opener)
        for i in (0,1):
            body=payload(None,server='Korell',username='Test',poll_seconds=180,now_ms=NOW+i)
            publisher.publish(body,NOW+i,image=png)
        self.assertEqual([r.method for r in opener.requests],['POST','PATCH'])
        for i,request in enumerate(opener.requests):
            mime=BytesParser(policy=policy.default).parsebytes(
                ('Content-Type: '+request.get_header('Content-type')+'\r\nMIME-Version: 1.0\r\n\r\n').encode()+request.data)
            parts=list(mime.iter_parts())
            self.assertEqual(parts[0].get_param('name',header='Content-Disposition'),'payload_json')
            data=json.loads(parts[0].get_payload(decode=True))
            self.assertEqual(data['attachments'],[{'id':0,'filename':f'remnants-{NOW+i}.png','description':'Remnant-Träger auf Korell. '}])
            self.assertEqual(data['allowed_mentions'],{'parse':[]})
            self.assertEqual(parts[1].get_param('name',header='Content-Disposition'),'files[0]')
            self.assertEqual(parts[1].get_payload(decode=True),png)

    def test_discord_must_confirm_replacement_attachment(self):
        from pg_remnants.card import payload
        body=payload(None,server='Korell',username='Test',poll_seconds=180,now_ms=NOW)
        with self.assertRaises(DiscordError):
            Publisher(URL,self.store,opener=Opener([{'id':'11','channel_id':'22','attachments':[]}, {'id':'11','channel_id':'22','attachments':[]}])).publish(
                body,NOW,image=b'\x89PNG\r\n\x1a\nexample')

    def test_file_consumed_into_embed_is_confirmed_without_separate_attachment(self):
        from pg_remnants.card import payload
        body=payload(None,server='Korell',username='Test',poll_seconds=180,now_ms=NOW)
        response={'id':'11','channel_id':'22','attachments':[],
                  'embeds':[{'image':{'url':f'https://cdn.discordapp.com/attachments/22/123/remnants-{NOW}.png'}}]}
        receipt=Publisher(URL,self.store,opener=Opener([response])).publish(body,NOW,image=b'\x89PNG\r\n\x1a\nexample')
        self.assertEqual(receipt['attachment_id'],'123')
