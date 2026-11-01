"""One-time owner browser consent + existing-folder Picker. Never prints tokens."""
import argparse
import hmac
import io
import json
import os
from pathlib import Path
import secrets
import subprocess
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

from .worker import CHANNEL, FOLDER

SCOPE = 'https://www.googleapis.com/auth/drive.file'
REDIRECT = 'http://localhost:8765/callback'


def make_config(credentials, api):
    from googleapiclient.http import MediaIoBaseUpload
    if not credentials.refresh_token:
        raise ValueError('Offline refresh token required; repeat consent with prompt=consent')
    if set(credentials.granted_scopes or credentials.scopes or []) != {SCOPE}:
        raise ValueError('Unexpected actual granted scopes')
    oauth = json.loads(credentials.to_json())
    # A short-lived access token and expiry need not be stored in GitHub.
    oauth.pop('token', None)
    oauth.pop('expiry', None)
    if set(oauth.get('scopes', [])) != {SCOPE}:
        raise ValueError('Unexpected scopes; refuse broader authorization')
    folder = api.files().get(fileId=FOLDER, fields='mimeType,capabilities(canAddChildren)').execute()
    if folder['mimeType'] != 'application/vnd.google-apps.folder' or not folder.get('capabilities', {}).get('canAddChildren'):
        raise ValueError('Selected folder must be writable by this app')
    matches = api.files().list(q=f"'{FOLDER}' in parents and trashed=false and appProperties has {{key='xtr_role' and value='manifest'}}",
                              fields='files(id),nextPageToken', pageSize=100).execute()
    if matches.get('nextPageToken') or len(matches['files']) > 1:
        raise ValueError('Multiple recovery manifests: owner review required')
    if matches['files']:
        manifest_id = matches['files'][0]['id']
    else:
        content = json.dumps({'version': 1, 'channel': CHANNEL, 'videos': {}}).encode()
        manifest_id = api.files().create(body={'name': 'Xbox Twitch Recorder recovery.json', 'parents': [FOLDER],
            'appProperties': {'xtr_role': 'manifest'}},
            media_body=MediaIoBaseUpload(io.BytesIO(content), mimetype='application/json'), fields='id').execute(num_retries=0)['id']
    return {'oauth': oauth, 'manifest_id': manifest_id}


def persist(config, output, github_secret):
    data = json.dumps(config).encode()
    if github_secret:
        # Send only through stdin; never command arguments, console or git.
        result = subprocess.run(['gh', 'secret', 'set', 'XTR_DRIVE_AUTH', '--repo',
                                 'coltonhavens/xbox-twitch-recorder'], input=data, capture_output=True, timeout=60)
        if result.returncode:
            raise RuntimeError('GitHub secret write failed; no credentials printed')
    else:
        fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as destination:
            destination.write(data)


def main():
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
    parser = argparse.ArgumentParser()
    parser.add_argument('--client-file', required=True, type=Path)
    parser.add_argument('--picker-key-file', required=True, type=Path)
    parser.add_argument('--project-number', required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--github-secret', action='store_true')
    group.add_argument('--output', type=Path, help='New mode-0600 file; never commit it')
    args = parser.parse_args()
    os.umask(0o077)
    config = json.loads(args.client_file.read_text())
    if 'web' not in config or REDIRECT not in config['web'].get('redirect_uris', []):
        raise SystemExit('Use the approved Web OAuth client with exact localhost callback; no settings changed')
    if not args.project_number.isdigit():
        raise SystemExit('Project number must be numeric')
    flow = Flow.from_client_config(config, scopes=[SCOPE], redirect_uri=REDIRECT, autogenerate_code_verifier=True)
    auth_url, state = flow.authorization_url(access_type='offline', prompt='consent', include_granted_scopes='false')
    nonce, browser_session = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    key = args.picker_key_file.read_text().strip()
    complete = False

    class Handler(BaseHTTPRequestHandler):
        credentials = None
        def log_message(self, *_):
            pass  # Callback codes, tokens and query strings must never enter logs.
        def allowed(self):
            return self.headers.get('Host') in ('localhost:8765', '127.0.0.1:8765')
        def send(self, body, status=200, content_type='text/html; charset=utf-8', cookie=False):
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'strict-origin')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'none'; script-src 'nonce-"+nonce+"' https://apis.google.com https://*.gstatic.com https://*.google.com; frame-src https://*.google.com; connect-src 'self' https://*.googleapis.com https://*.google.com; style-src 'unsafe-inline'; img-src https://*.google.com https://*.gstatic.com")
            if cookie:
                self.send_header('Set-Cookie', 'xtr_session='+browser_session+'; HttpOnly; SameSite=Lax; Path=/')
            self.end_headers()
            self.wfile.write(body.encode())
        def do_GET(self):
            if not self.allowed():
                return self.send('Invalid host', 400)
            parts = urllib.parse.urlsplit(self.path)
            if parts.path == '/':
                import html
                return self.send('<h1>Authorize Xbox Twitch Recorder</h1><a href="'+html.escape(auth_url, quote=True)+'">Authorize Google Drive</a>', cookie=True)
            if parts.path != '/callback':
                return self.send('Not found', 404)
            query = urllib.parse.parse_qs(parts.query)
            if ('xtr_session='+browser_session not in self.headers.get('Cookie', '') or
                    not hmac.compare_digest(query.get('state', [''])[0], state) or not query.get('code')):
                return self.send('Invalid or denied authorization', 400)
            try:
                flow.fetch_token(code=query['code'][0], timeout=30)
                self.__class__.credentials = flow.credentials
                if set(flow.credentials.granted_scopes or flow.credentials.scopes or []) != {SCOPE}:
                    raise ValueError('Unexpected scope')
                # Only short-lived access token goes to local Picker; refresh/client secrets stay server-side.
                values = json.dumps({'token': flow.credentials.token, 'key': key,
                                     'project': args.project_number, 'nonce': nonce}).replace('<', '\\u003c')
                page = '''<h1>Select the existing archive folder</h1><p>Choose the folder ending VXjvAYBG. Other selections are rejected.</p><p id="status"></p>
<script nonce="NONCE">const c=VALUES;
function picked(data){if(data.action===google.picker.Action.PICKED){fetch('/finish',{method:'POST',headers:{'Content-Type':'application/json','X-XTR-CSRF':c.nonce},body:JSON.stringify({id:data.docs[0].id})}).then(async r=>{document.getElementById('status').textContent=await r.text()});}}
function ready(){const view=new google.picker.DocsView(google.picker.ViewId.FOLDERS).setIncludeFolders(true).setSelectFolderEnabled(true);new google.picker.PickerBuilder().addView(view).setOAuthToken(c.token).setDeveloperKey(c.key).setAppId(c.project).setOrigin(window.location.origin).setCallback(picked).build().setVisible(true);}
function loaded(){gapi.load('picker',ready);}</script><script nonce="NONCE" src="https://apis.google.com/js/api.js?onload=loaded"></script>'''.replace('VALUES', values).replace('NONCE', nonce)
                return self.send(page)
            except Exception:
                return self.send('Authorization failed. No credentials were printed. Review client and consent settings.', 400)
        def do_POST(self):
            nonlocal complete
            if (not self.allowed() or self.path != '/finish' or self.headers.get('Origin') != 'http://localhost:8765' or
                    'xtr_session='+browser_session not in self.headers.get('Cookie', '') or
                    not hmac.compare_digest(self.headers.get('X-XTR-CSRF', ''), nonce) or not self.credentials):
                return self.send('Invalid request', 403)
            try:
                length = int(self.headers.get('Content-Length', '0'))
                if not 0 < length < 2048:
                    raise ValueError('Invalid body size')
                if json.loads(self.rfile.read(length)).get('id') != FOLDER:
                    raise ValueError('Wrong folder')
                api = build('drive', 'v3', credentials=self.credentials, cache_discovery=False)
                result = make_config(self.credentials, api)
                persist(result, args.output, args.github_secret)
                complete = True
                self.send('Drive authorized and recovery manifest ready. You can close this window. Automation remains disabled.')
            except Exception:
                self.send('Folder authorization or secure save failed. Select the exact folder and review local setup.', 400)

    class LoopbackServer(HTTPServer):
        def get_request(self):
            connection, address = super().get_request()
            connection.settimeout(10)
            return connection, address

    # Loopback only, fixed host validation protects against DNS rebinding.
    with LoopbackServer(('127.0.0.1', 8765), Handler) as server:
        server.timeout = 1
        print('Open http://localhost:8765 in your browser. No credentials will be printed.', flush=True)
        deadline = __import__('time').monotonic() + 900
        while not complete and __import__('time').monotonic() < deadline:
            server.handle_request()
    if not complete:
        raise SystemExit('Authorization expired; no activation performed')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'success': False, 'error_type': type(exc).__name__}))
        raise SystemExit(1)
