import http.client
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock
from recorder.authorize_drive import make_config, SCOPE


class DriveSetupTests(unittest.TestCase):
    def credentials(self):
        credentials = Mock(refresh_token='fake-refresh', granted_scopes=[SCOPE], scopes=[SCOPE])
        credentials.to_json.return_value = json.dumps({'token':'short-lived-token','expiry':'unused',
            'refresh_token':'fake-refresh','client_id':'fake-id','client_secret':'fake-secret','scopes':[SCOPE],
            'token_uri':'https://oauth2.googleapis.com/token'})
        return credentials

    def test_missing_refresh_and_broader_scopes_fail_before_any_drive_request(self):
        for refresh, scope in ((None,[SCOPE]), ('fake',['https://www.googleapis.com/auth/drive'])):
            credentials = self.credentials()
            credentials.refresh_token, credentials.granted_scopes = refresh, scope
            api = Mock()
            with self.assertRaises(ValueError):
                make_config(credentials, api)
            api.files.assert_not_called()

    def test_reauthorization_reuses_manifest_and_does_not_store_access_token(self):
        api = Mock()
        api.files.return_value.get.return_value.execute.return_value = {
            'mimeType':'application/vnd.google-apps.folder','capabilities':{'canAddChildren':True}}
        api.files.return_value.list.return_value.execute.return_value = {'files':[{'id':'existing-manifest'}]}
        result = make_config(self.credentials(), api)
        self.assertEqual(result['manifest_id'], 'existing-manifest')
        self.assertNotIn('token', result['oauth'])
        self.assertNotIn('expiry', result['oauth'])
        api.files.return_value.create.assert_not_called()

    def test_duplicate_manifests_fail_closed_without_reinitializing_state(self):
        api = Mock()
        api.files.return_value.get.return_value.execute.return_value = {
            'mimeType':'application/vnd.google-apps.folder','capabilities':{'canAddChildren':True}}
        api.files.return_value.list.return_value.execute.return_value = {'files':[{'id':'first'},{'id':'second'}]}
        with self.assertRaises(ValueError):
            make_config(self.credentials(), api)
        api.files.return_value.create.assert_not_called()

    def test_real_loopback_server_rejects_bad_host_callback_and_cross_origin_post(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            client = root/'client.json'
            client.write_text(json.dumps({'web':{'project_id':'xbox-twitch-recorder','client_id':'fake-client','client_secret':'fake-client-secret',
                'auth_uri':'https://accounts.google.com/o/oauth2/auth','token_uri':'https://oauth2.googleapis.com/token',
                'redirect_uris':['http://localhost:8765/callback']}}))
            key = root/'key.txt'
            key.write_text('fake-picker-key')
            child = subprocess.Popen([sys.executable,'-m','recorder.authorize_drive','--client-file',str(client),
                '--picker-key-file',str(key),'--project-number','123','--output',str(root/'auth.json')],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                def request(method, route, headers=None):
                    connection = http.client.HTTPConnection('127.0.0.1',8765,timeout=2)
                    connection.request(method, route, headers=headers or {'Host':'localhost:8765'})
                    response = connection.getresponse()
                    data = response.read().decode()
                    result = response.status, dict(response.getheaders()), data
                    connection.close()
                    return result
                deadline = time.monotonic()+5
                while True:
                    if child.poll() is not None:
                        self.fail('Test server did not start')
                    try:
                        status, headers, body = request('GET','/')
                        break
                    except ConnectionError:
                        if time.monotonic() >= deadline:
                            raise
                        time.sleep(.05)
                self.assertEqual(status,200)
                self.assertIn('HttpOnly',headers['Set-Cookie'])
                self.assertEqual(headers['Cache-Control'],'no-store')
                self.assertEqual(headers['Referrer-Policy'],'strict-origin')
                self.assertNotIn('fake-client-secret',body)
                self.assertEqual(request('GET','/',{'Host':'evil.invalid'})[0],400)
                self.assertEqual(request('GET','/callback?code=fake&state=wrong')[0],400)
                self.assertEqual(request('POST','/finish',{'Host':'localhost:8765','Origin':'https://evil.invalid'})[0],403)
                self.assertFalse((root/'auth.json').exists())
            finally:
                child.terminate()
                stdout, stderr = child.communicate(timeout=5)
                self.assertNotIn(b'fake-client-secret', stdout+stderr)
