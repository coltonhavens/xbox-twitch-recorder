import base64
import hashlib
import http.client
import json
import threading
import unittest
from http.server import ThreadingHTTPServer
from unittest.mock import Mock
from broker.server import Broker, Remote, SafeError, configuration, handler, seal, FOLDER, SCOPE


def settings():
    return configuration({'BROKER_ENABLED':'true','BROKER_ORIGIN':'https://connect.example.test',
        'GOOGLE_WEB_CLIENT_JSON':json.dumps({'web':{'project_id':'xbox-twitch-recorder',
            'client_id':'fake-client','client_secret':'private-client-secret',
            'token_uri':'https://oauth2.googleapis.com/token','javascript_origins':['https://connect.example.test','http://localhost:8765']}}),
        'OWNER_GOOGLE_EMAIL':'owner@example.test',
        'GITHUB_SECRET_WRITER_TOKEN':'private-github-token','PICKER_API_KEY':'browser-picker-key',
        'GOOGLE_PROJECT_NUMBER':'123'})


class FakeRemote:
    def __init__(self):
        from nacl.public import PrivateKey
        self.private = PrivateKey.generate()
        self.key = {'key':base64.b64encode(bytes(self.private.public_key)).decode(),'key_id':'key-id'}
        self.write_calls = []
        self.config_calls = 0
        self.preflight_calls = 0
    def preflight(self):
        self.preflight_calls += 1
        return self.key
    def exchange(self, code):
        return Mock(token='short-access-token')
    def drive_config(self, credentials):
        self.config_calls += 1
        return {'oauth':{'refresh_token':'private-refresh-token','scopes':[SCOPE]},'manifest_id':'manifest'}
    def write(self, payload, key):
        self.write_calls.append(seal(payload,key['key']))


class BrowserBrokerTests(unittest.TestCase):
    def test_disabled_service_cannot_start(self):
        with self.assertRaises(SafeError):
            configuration({})

    def test_existing_client_project_and_exact_origin_are_required(self):
        config = settings()
        self.assertEqual(config['client']['project_id'],'xbox-twitch-recorder')
        self.assertIn('http://localhost:8765',config['client']['javascript_origins'])
        with self.assertRaises(SafeError):
            configuration({'BROKER_ENABLED':'true','BROKER_ORIGIN':'http://localhost:8765'})

    def test_sealed_secret_roundtrips_only_with_private_key(self):
        from nacl.public import SealedBox
        remote = FakeRemote()
        payload = {'oauth':{'refresh_token':'private-refresh-token'}}
        encrypted = seal(payload,remote.key['key'])
        self.assertNotIn('private-refresh-token',encrypted)
        self.assertEqual(json.loads(SealedBox(remote.private).decrypt(base64.b64decode(encrypted))),payload)

    def test_owner_identity_rejected_before_credentials_reach_picker(self):
        remote = Remote(settings())
        remote.http = Mock()
        remote.http.post.return_value.status_code = 200
        remote.http.post.return_value.json.return_value = {'access_token':'access','refresh_token':'refresh',
            'token_type':'Bearer','scope':SCOPE}
        remote.http.get.return_value.status_code = 200
        remote.http.get.return_value.json.return_value = {'user':{'emailAddress':'wrong@example.test'}}
        with self.assertRaises(SafeError):
            remote.exchange('code')

    def test_folder_and_csrf_binding(self):
        remote = FakeRemote()
        broker = Broker(settings(),remote)
        sid,public = broker.start()
        with self.assertRaises(SafeError):
            broker.code(sid,'wrong','code')
        result = broker.code(sid,public['csrf'],'one-time-code')
        self.assertEqual(result,{'accessToken':'short-access-token'})
        self.assertNotIn('refresh',json.dumps(result))
        with self.assertRaises(SafeError):
            broker.finish(sid,public['csrf'],'wrong-folder')
        self.assertEqual(remote.write_calls,[])
        self.assertEqual(broker.finish(sid,public['csrf'],FOLDER),{'connected':True,'recordingActive':False})
        self.assertEqual(broker.sessions,{})
        with self.assertRaises(SafeError):
            broker.start()

    def test_expired_session_and_replayed_code_rejected(self):
        clock = [0]
        broker = Broker(settings(),FakeRemote(),now=lambda:clock[0])
        sid,public = broker.start()
        broker.code(sid,public['csrf'],'once')
        with self.assertRaises(SafeError):
            broker.code(sid,public['csrf'],'again')
        clock[0] = 601
        with self.assertRaises(SafeError):
            broker.finish(sid,public['csrf'],FOLDER)
        self.assertEqual(broker.sessions,{})

    def test_github_failure_does_not_recreate_manifest_on_retry(self):
        remote = FakeRemote()
        original = remote.write
        remote.write = Mock(side_effect=[SafeError('retry'),None])
        broker = Broker(settings(),remote)
        sid,public = broker.start()
        broker.code(sid,public['csrf'],'once')
        with self.assertRaises(SafeError):
            broker.finish(sid,public['csrf'],FOLDER)
        broker.finish(sid,public['csrf'],FOLDER)
        self.assertEqual(remote.config_calls,1)

    def test_real_http_flow_keeps_codes_and_refresh_out_of_urls_and_responses(self):
        broker = Broker(settings(),FakeRemote())
        server = ThreadingHTTPServer(('127.0.0.1',0),handler(broker))
        thread = threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        try:
            def request(method,path,body=None,extra=None):
                connection = http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3)
                headers = {'Host':'connect.example.test','Origin':'https://connect.example.test',
                    'Content-Type':'application/json','X-Requested-With':'XMLHttpRequest'}
                headers.update(extra or {})
                connection.request(method,path,json.dumps(body) if body is not None else None,headers)
                response = connection.getresponse()
                result = response.status,dict(response.getheaders()),response.read().decode()
                connection.close()
                return result
            status,headers,page = request('GET','/')
            self.assertEqual(status,200)
            self.assertNotIn('private-client-secret',page)
            self.assertNotIn('private-github-token',page)
            self.assertEqual(request('GET','/?code=never-in-url')[0],400)
            self.assertEqual(request('POST','/start',{}, {'Origin':'https://evil.invalid'})[0],403)
            status,headers,text = request('POST','/start',{})
            self.assertEqual(status,200)
            self.assertIn('Secure',headers['Set-Cookie'])
            self.assertIn('HttpOnly',headers['Set-Cookie'])
            public = json.loads(text)
            private_headers = {'Cookie':headers['Set-Cookie'].split(';')[0],'X-XTR-CSRF':public['csrf']}
            status,headers,text = request('POST','/code',{'code':'fake-code'},private_headers)
            self.assertEqual(status,200)
            self.assertNotIn('private-refresh-token',text)
            self.assertNotIn('private-client-secret',text)
            status,headers,text = request('POST','/finish',{'folderId':FOLDER},private_headers)
            self.assertEqual(status,200)
            self.assertEqual(json.loads(text),{'connected':True,'recordingActive':False})
            self.assertNotIn('private-refresh-token',text)
            self.assertEqual(len(broker.remote.write_calls),1)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_google_response_must_have_exact_scope_and_refresh_token(self):
        remote = Remote(settings())
        remote.http = Mock()
        response = remote.http.post.return_value
        response.status_code = 200
        for token in ({'access_token':'access','scope':SCOPE,'token_type':'Bearer'},
                      {'access_token':'access','refresh_token':'refresh','scope':'https://www.googleapis.com/auth/drive','token_type':'Bearer'}):
            response.json.return_value = token
            with self.assertRaises(SafeError):
                remote.exchange('code')

    def test_github_request_contains_only_sealed_config(self):
        remote = Remote(settings())
        fake = FakeRemote()
        remote.github = Mock(return_value={})
        remote.write({'oauth':{'refresh_token':'private-refresh-token'}},fake.key)
        args = remote.github.call_args.args
        self.assertEqual(args[:2],('PUT','/actions/secrets/XTR_DRIVE_AUTH'))
        self.assertEqual(set(args[2]),{'encrypted_value','key_id'})
        self.assertNotIn('private-refresh-token',json.dumps(args[2]))
