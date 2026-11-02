"""Temporary owner-only HTTPS authorization broker. Source only; no deployment."""
import base64
import hmac
import json
import os
import re
from pathlib import Path
import secrets
import threading
import time
import urllib.parse
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from recorder.authorize_drive import make_config, SCOPE
from recorder.worker import FOLDER

REPO = 'coltonhavens/xbox-twitch-recorder'
PROJECT = 'xbox-twitch-recorder'
TTL = 600


class SafeError(Exception):
    pass


def configuration(env):
    if env.get('BROKER_ENABLED') != 'true':
        raise SafeError('Connection service is disabled')
    origin = env.get('BROKER_ORIGIN', '')
    parsed = urllib.parse.urlsplit(origin)
    if (parsed.scheme != 'https' or not parsed.hostname or parsed.path or parsed.query or
            parsed.fragment or parsed.username or parsed.port not in (None, 443)):
        raise SafeError('Configure the approved HTTPS origin')
    separate = bool(env.get('GOOGLE_CLIENT_ID') or env.get('GOOGLE_CLIENT_SECRET'))
    if separate and env.get('GOOGLE_WEB_CLIENT_JSON'):
        raise SafeError('Configure either separate client fields or the original JSON, not both')
    if separate:
        number = env.get('GOOGLE_PROJECT_NUMBER', '')
        client_id = env.get('GOOGLE_CLIENT_ID', '').strip()
        secret = env.get('GOOGLE_CLIENT_SECRET', '').strip()
        if (not number.isdigit() or not secret or
                not re.fullmatch(re.escape(number) + r'-[A-Za-z0-9_-]+\.apps\.googleusercontent\.com', client_id)):
            raise SafeError('Configure the existing Google client ID, secret and matching project number')
        # Local format/project-number check only. Google must independently accept
        # the exact hosted origin; this does not claim its Console settings changed.
        client = {'project_id':PROJECT, 'client_id':client_id, 'client_secret':secret,
                  'token_uri':'https://oauth2.googleapis.com/token'}
    else:
        try:
            client = json.loads(env['GOOGLE_WEB_CLIENT_JSON'])['web']
        except (KeyError, ValueError, TypeError):
            raise SafeError('Configure the existing Web client securely')
        if (not isinstance(client, dict) or client.get('project_id') != PROJECT or
                origin not in client.get('javascript_origins', []) or
                not client.get('client_id') or not client.get('client_secret') or
                client.get('token_uri') != 'https://oauth2.googleapis.com/token'):
            raise SafeError('Existing client must match the project and approved HTTPS origin')
    owner = env.get('OWNER_GOOGLE_EMAIL', '').strip().casefold()
    if '@' not in owner or not env.get('GITHUB_SECRET_WRITER_TOKEN') or not env.get('PICKER_API_KEY') or not env.get('GOOGLE_PROJECT_NUMBER', '').isdigit():
        raise SafeError('Secure owner, GitHub and Picker configuration required')
    return {'origin': origin, 'host': parsed.netloc, 'client': client, 'owner_email': owner,
            'github_token': env['GITHUB_SECRET_WRITER_TOKEN'],
            'picker_key': env['PICKER_API_KEY'], 'project_number': env['GOOGLE_PROJECT_NUMBER']}


def seal(payload, public_key):
    from nacl.public import PublicKey, SealedBox
    key = base64.b64decode(public_key, validate=True)
    if len(key) != 32:
        raise SafeError('Invalid GitHub public key')
    return base64.b64encode(SealedBox(PublicKey(key)).encrypt(json.dumps(payload).encode())).decode()


class Remote:
    def __init__(self, config):
        import requests
        self.http = requests.Session()
        self.config = config

    def github(self, method, path, body=None):
        response = self.http.request(method, 'https://api.github.com/repos/'+REPO+path,
            headers={'Authorization':'Bearer '+self.config['github_token'], 'Accept':'application/vnd.github+json',
                     'X-GitHub-Api-Version':'2022-11-28'}, json=body, timeout=30, allow_redirects=False)
        if response.status_code not in (200, 201, 204):
            raise SafeError('GitHub authorization failed; no secret values displayed')
        return response.json() if response.status_code == 200 else {}

    def preflight(self):
        repo = self.github('GET', '')
        if str(repo.get('id')) != '1442216654' or str(repo.get('owner', {}).get('id')) != '230064597':
            raise SafeError('Unexpected target repository identity')
        key = self.github('GET', '/actions/secrets/public-key')
        if not key.get('key') or not key.get('key_id'):
            raise SafeError('Cannot read the target repository secret public key')
        return key

    def exchange(self, code):
        client = self.config['client']
        response = self.http.post('https://oauth2.googleapis.com/token', data={
            'client_id':client['client_id'], 'client_secret':client['client_secret'],
            'code':code, 'grant_type':'authorization_code', 'redirect_uri':self.config['origin']},
            timeout=30, allow_redirects=False)
        if response.status_code != 200:
            raise SafeError('Google consent exchange failed; restart the connection')
        token = response.json()
        if (set(token.get('scope', '').split()) != {SCOPE} or not token.get('refresh_token') or
                not token.get('access_token') or str(token.get('token_type', '')).lower() != 'bearer'):
            raise SafeError('Exactly drive.file and offline refresh access are required')
        # about.get supports drive.file: verify owner without requesting email/openid scopes.
        identity = self.http.get('https://www.googleapis.com/drive/v3/about',
            params={'fields':'user(emailAddress)'}, headers={'Authorization':'Bearer '+token['access_token']},
            timeout=30, allow_redirects=False)
        if (identity.status_code != 200 or identity.json().get('user', {}).get('emailAddress', '').casefold() != self.config['owner_email']):
            raise SafeError('Sign in with the owner Google account')
        from google.oauth2.credentials import Credentials
        return Credentials(token=token['access_token'], refresh_token=token['refresh_token'],
            client_id=client['client_id'], client_secret=client['client_secret'],
            token_uri='https://oauth2.googleapis.com/token', scopes=[SCOPE], granted_scopes=[SCOPE])

    def drive_config(self, credentials):
        import httplib2
        from google_auth_httplib2 import AuthorizedHttp
        from googleapiclient.discovery import build
        api = build('drive','v3',http=AuthorizedHttp(credentials,http=httplib2.Http(timeout=30)),cache_discovery=False)
        return make_config(credentials, api)

    def write(self, payload, key):
        encrypted = seal(payload, key['key'])
        self.github('PUT','/actions/secrets/XTR_DRIVE_AUTH', {'encrypted_value':encrypted, 'key_id':key['key_id']})


class Broker:
    def __init__(self, config, remote, now=time.monotonic):
        self.config, self.remote, self.now = config, remote, now
        self.sessions = {}
        self.lock = threading.RLock()
        self.finished = False
        self.login_attempts = []

    def clean(self):
        for key in list(self.sessions):
            if self.now() >= self.sessions[key]['expires']:
                del self.sessions[key]

    def start(self):
        with self.lock:
            self.clean()
            self.login_attempts = [at for at in self.login_attempts if self.now()-at < TTL]
            if self.finished or len(self.login_attempts) >= 20 or len(self.sessions) >= 10:
                raise SafeError('Connection temporarily unavailable; owner must review/restart the service')
            self.login_attempts.append(self.now())
            key = self.remote.preflight()  # Check repository access BEFORE Google consent.
            sid = secrets.token_urlsafe(32)
            session = {'csrf':secrets.token_urlsafe(32), 'expires':self.now()+TTL, 'key':key}
            self.sessions[sid] = session
            return sid, self.public(session)

    def public(self, session):
        return {'csrf':session['csrf'], 'clientId':self.config['client']['client_id'],
                'pickerKey':self.config['picker_key'], 'projectNumber':self.config['project_number']}

    def session(self, sid, csrf=None):
        self.clean()
        session = self.sessions.get(sid)
        if self.finished or not session or (csrf is not None and not hmac.compare_digest(session['csrf'],csrf)):
            raise SafeError('Connection expired or invalid; reload this page')
        return session

    def code(self, sid, csrf, code):
        with self.lock:
            session = self.session(sid,csrf)
            if session.get('code_used') or not code or len(code) > 4096:
                raise SafeError('Invalid or already-used consent code')
            session['code_used'] = True
            credentials = self.remote.exchange(code)
            session['credentials'] = credentials
            # Only the short-lived access token reaches owner Picker over HTTPS response body.
            return {'accessToken':credentials.token}

    def finish(self, sid, csrf, folder):
        with self.lock:
            session = self.session(sid,csrf)
            if folder != FOLDER or not session.get('credentials'):
                raise SafeError('Select the existing designated Drive folder')
            if not session.get('payload'):
                session['payload'] = self.remote.drive_config(session['credentials'])
            self.remote.write(session['payload'],session['key'])
            self.sessions.clear()  # No refresh token remains in application session storage.
            self.finished = True
            return {'connected':True, 'recordingActive':False}


def handler(broker):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*_):
            pass  # No paths, bodies, cookies, auth codes or token-related errors in logs.
        def send(self,status,payload,html=False):
            data = payload.encode() if html else json.dumps(payload).encode()
            self.send_response(status)
            self.send_header('Content-Type','text/html; charset=utf-8' if html else 'application/json')
            self.send_header('Cache-Control','no-store')
            self.send_header('Referrer-Policy','strict-origin')
            self.send_header('X-Frame-Options','DENY')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Cross-Origin-Opener-Policy','same-origin-allow-popups')
            self.send_header('Content-Security-Policy',"default-src 'none'; script-src 'self' https://accounts.google.com https://apis.google.com https://*.gstatic.com https://*.google.com; connect-src 'self' https://accounts.google.com https://*.googleapis.com https://*.google.com; frame-src https://accounts.google.com https://*.google.com; style-src 'self'; img-src https://*.google.com https://*.gstatic.com; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
            for key,value in getattr(self,'extra_headers',{}).items():
                self.send_header(key,value)
            self.end_headers()
            self.wfile.write(data)
        def do_GET(self):
            if '?' in self.path or self.headers.get('Host') != broker.config['host']:
                return self.send(400,{'error':'Invalid request'})
            resources = {'/':('index.html','text/html'),'/app.js':('app.js','text/javascript'),'/style.css':('style.css','text/css')}
            if self.path not in resources:
                return self.send(404,{'error':'Not found'})
            file,kind = resources[self.path]
            # Static assets have no template-substituted credentials or config values.
            data = (Path(__file__).parent/'static'/file).read_bytes()
            self.send_response(200)
            self.send_header('Content-Type',kind+'; charset=utf-8')
            self.send_header('Cache-Control','no-store')
            self.send_header('Referrer-Policy','strict-origin')
            self.send_header('X-Frame-Options','DENY')
            self.send_header('X-Content-Type-Options','nosniff')
            self.send_header('Cross-Origin-Opener-Policy','same-origin-allow-popups')
            self.send_header('Content-Security-Policy',"default-src 'none'; script-src 'self' https://accounts.google.com https://apis.google.com https://*.gstatic.com https://*.google.com; connect-src 'self' https://accounts.google.com https://*.googleapis.com https://*.google.com; frame-src https://accounts.google.com https://*.google.com; style-src 'self'; img-src https://*.google.com https://*.gstatic.com; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(data)
        def do_POST(self):
            if (self.headers.get('Host') != broker.config['host'] or
                    self.headers.get('Origin') != broker.config['origin'] or
                    self.headers.get('X-Requested-With') != 'XMLHttpRequest' or
                    self.headers.get('Content-Type') != 'application/json'):
                return self.send(403,{'error':'Invalid origin or request'})
            try:
                length = int(self.headers.get('Content-Length','0'))
                if not 0 < length <= 8192:
                    raise SafeError('Invalid request size')
                body = json.loads(self.rfile.read(length))
                if self.path == '/start':
                    sid,result = broker.start()
                    self.extra_headers = {'Set-Cookie':'xtr_owner='+sid+'; Secure; HttpOnly; SameSite=Strict; Path=/; Max-Age='+str(TTL)}
                else:
                    cookies = SimpleCookie(self.headers.get('Cookie',''))
                    sid = cookies['xtr_owner'].value if 'xtr_owner' in cookies else ''
                    csrf = self.headers.get('X-XTR-CSRF','')
                    if self.path == '/code':
                        result = broker.code(sid,csrf,body.get('code',''))
                    elif self.path == '/finish':
                        result = broker.finish(sid,csrf,body.get('folderId',''))
                        self.extra_headers = {'Set-Cookie':'xtr_owner=; Secure; HttpOnly; SameSite=Strict; Path=/; Max-Age=0'}
                    else:
                        raise SafeError('Not found')
                return self.send(200,result)
            except SafeError as exc:
                return self.send(400,{'error':str(exc)})
            except Exception:
                return self.send(400,{'error':'Connection failed; no credentials displayed. Review owner configuration.'})
    return Handler


def main():
    config = configuration(os.environ)
    broker = Broker(config,Remote(config))
    def expire_sessions():
        while True:
            time.sleep(30)
            with broker.lock:
                broker.clean()
    threading.Thread(target=expire_sessions,daemon=True).start()
    class Server(ThreadingHTTPServer):
        daemon_threads = True
        def get_request(self):
            connection,address = super().get_request()
            connection.settimeout(15)
            return connection,address
    # Bind behind the approved host's TLS proxy. No direct public HTTP access is approved.
    with Server(('0.0.0.0',int(os.environ.get('PORT','10000'))),handler(broker)) as server:
        server.serve_forever()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        raise SystemExit('Authorization broker unavailable; configure privately. No deployment or recording activation performed.')
