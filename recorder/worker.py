"""Single-host live Twitch archiver. No cloud provisioning or browser endpoints."""
import concurrent.futures
import fcntl
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import shutil
import signal
import sqlite3
import subprocess
import threading
import time
import uuid
import urllib.error
import urllib.request
import urllib.parse

LOG = logging.getLogger('recorder')
STOP = threading.Event()
FOLDER = '1X9VfSes_byvkygreHfdvGNHzVXjvAYBG'


def digest(path, algorithm='sha256'):
    h = hashlib.new(algorithm)
    with open(path, 'rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


class Journal:
    def __init__(self, path):
        self.db = sqlite3.connect(path)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('CREATE TABLE IF NOT EXISTS chunks (name TEXT PRIMARY KEY, sha TEXT NOT NULL, drive_id TEXT, uploaded INTEGER NOT NULL DEFAULT 0)')

    def stage(self, path):
        sha = digest(path)
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO chunks(name,sha) VALUES (?,?)', (path.name, sha))
        row = self.db.execute('SELECT sha,drive_id,uploaded FROM chunks WHERE name=?', (path.name,)).fetchone()
        if row[0] != sha:
            raise RuntimeError('Immutable chunk changed')
        return row

    def identify(self, name, file_id):
        with self.db:
            self.db.execute('UPDATE chunks SET drive_id=? WHERE name=?', (file_id, name))

    def complete(self, name):
        with self.db:
            self.db.execute('UPDATE chunks SET uploaded=1 WHERE name=?', (name,))


def probe(path):
    result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries',
                             'stream=codec_type:format=duration', '-of', 'json', str(path)],
                            capture_output=True, timeout=60, check=True)
    data = json.loads(result.stdout)
    if not any(s['codec_type'] == 'video' for s in data.get('streams', [])):
        raise ValueError('No video stream')
    if float(data.get('format', {}).get('duration', 0)) <= 0:
        raise ValueError('Empty recording')
    return data


class Drive:
    def __init__(self, credentials_path):
        # This is an owner-authorized OAuth refresh token file, NEVER an SA key.
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        import httplib2
        from google_auth_httplib2 import AuthorizedHttp
        credentials = Credentials.from_authorized_user_file(credentials_path)
        if credentials.scopes != ['https://www.googleapis.com/auth/drive.file']:
            raise ValueError('Only drive.file scope is accepted')
        self.api = build('drive', 'v3', http=AuthorizedHttp(credentials, http=httplib2.Http(timeout=120)), cache_discovery=False)
        folder = self.api.files().get(fileId=FOLDER, fields='id,mimeType,capabilities(canAddChildren)', supportsAllDrives=True).execute()
        if folder['mimeType'] != 'application/vnd.google-apps.folder' or not folder.get('capabilities', {}).get('canAddChildren'):
            raise ValueError('Destination is not an authorized writable folder')

    def allocate(self):
        return self.api.files().generateIds(count=1, space='drive', type='files').execute()['ids'][0]

    def upload(self, path, file_id, sha):
        from googleapiclient.errors import HttpError
        from googleapiclient.http import MediaFileUpload
        try:
            remote = self.api.files().get(fileId=file_id, fields='id,size,md5Checksum,parents,appProperties', supportsAllDrives=True).execute()
        except HttpError as exc:
            if exc.resp.status != 404:
                raise
        else:
            return self.verify(path, remote, sha)
        request = self.api.files().create(
            body={'id': file_id, 'name': path.name, 'parents': [FOLDER], 'appProperties': {'xtr_sha256': sha}},
            media_body=MediaFileUpload(str(path), mimetype='video/MP2T', chunksize=8 * 1024 * 1024, resumable=True),
            fields='id,size,md5Checksum,parents,appProperties', supportsAllDrives=True)
        response = None
        while response is None:
            if STOP.is_set():
                raise InterruptedError('Upload paused')
            _, response = request.next_chunk(num_retries=5)
        return self.verify(path, response, sha)

    @staticmethod
    def verify(path, remote, sha):
        if (int(remote.get('size', -1)) != path.stat().st_size or
                remote.get('md5Checksum') != digest(path, 'md5') or
                FOLDER not in remote.get('parents', []) or
                remote.get('appProperties', {}).get('xtr_sha256') != sha):
            raise ValueError('Drive verification failed; keeping local chunk')
        return remote['id']


class Twitch:
    def __init__(self, client_id, client_secret, user_id):
        self.client_id, self.client_secret, self.user_id = client_id, client_secret, user_id
        self.token = None
        self.expiry = 0

    def live(self):
        if time.monotonic() >= self.expiry:
            body = urllib.parse.urlencode({'client_id': self.client_id, 'client_secret': self.client_secret,
                                           'grant_type': 'client_credentials'}).encode()
            with urllib.request.urlopen(urllib.request.Request('https://id.twitch.tv/oauth2/token', data=body), timeout=30) as r:
                token = json.load(r)
            self.token = token['access_token']
            self.expiry = time.monotonic() + max(1, token['expires_in'] - 60)
        req = urllib.request.Request('https://api.twitch.tv/helix/streams?user_id=' + self.user_id,
                                     headers={'Client-ID': self.client_id, 'Authorization': 'Bearer ' + self.token})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                streams = json.load(r)['data']
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                self.expiry = 0
            raise
        return streams[0] if streams else None


def stop_process(process):
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


def record(root, login, stream_id, seconds=300):
    """Capture live muxed video/audio; only publish closed segment files."""
    if not re.fullmatch(r'[a-zA-Z0-9_]{1,25}', login) or not str(stream_id).isdigit():
        raise ValueError('Invalid Twitch identity')
    session = root / ('capture-' + str(stream_id) + '-' + uuid.uuid4().hex)
    session.mkdir()
    # No tokens in command arguments, no shell, no signed playback URLs in logs.
    source = subprocess.Popen(['streamlink', '--loglevel', 'none', '--stream-timeout', '45',
                               '--stdout', 'https://www.twitch.tv/' + login, 'best'],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    target = None
    try:
        target = subprocess.Popen(['ffmpeg', '-nostdin', '-v', 'error', '-i', 'pipe:0',
                                   '-map', '0:v:0', '-map', '0:a?', '-c', 'copy', '-f', 'segment',
                                   '-segment_time', str(seconds), '-reset_timestamps', '1',
                                   '-segment_format', 'mpegts', str(session / '%08d.ts')],
                                  stdin=source.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        source.stdout.close()
        while target.poll() is None and not STOP.wait(2):
            publish(session, root, final=False)
            if shutil.disk_usage(root).free < 2 * 1024**3:
                raise RuntimeError('Low disk; stopping capture')
    finally:
        stop_process(source)
        if target is not None:
            try:
                target.wait(timeout=20)
            except subprocess.TimeoutExpired:
                stop_process(target)
        publish(session, root, final=True)


def publish(session, root, final):
    files = sorted(session.glob('*.ts'))
    for path in files if final else files[:-1]:
        # Final interrupted segment remains recoverable; uploader probes before use.
        os.replace(path, root / (session.name + '-' + path.name))
    if final:
        session.rmdir()


def upload_pass(root, journal, drive):
    for path in sorted(root.glob('capture-*.ts')):
        if STOP.is_set():
            break
        try:
            metadata = probe(path)
        except Exception as exc:
            quarantine = root / 'quarantine'
            quarantine.mkdir(exist_ok=True)
            os.replace(path, quarantine / path.name)
            LOG.error('chunk_quarantined name=%s error_type=%s', path.name, type(exc).__name__)
            continue
        try:
            if not any(s['codec_type'] == 'audio' for s in metadata['streams']):
                LOG.warning('chunk_without_audio name=%s', path.name)
            sha, file_id, uploaded = journal.stage(path)
            if not uploaded:
                if not file_id:
                    file_id = drive.allocate()
                    journal.identify(path.name, file_id)  # Durable BEFORE remote create.
                drive.upload(path, file_id, sha)
                journal.complete(path.name)
            path.unlink()  # Only after durable, verified completion.
            LOG.info('chunk_archived name=%s', path.name)
        except Exception as exc:
            LOG.warning('upload_pending name=%s error_type=%s', path.name, type(exc).__name__)
            # Avoid hot-looping/quota storms when Drive is unavailable.
            break


def uploader(root, credentials_path):
    journal = Journal(root / 'journal.sqlite3')
    drive = None
    while not STOP.is_set():
        try:
            if drive is None:
                drive = Drive(credentials_path)
            upload_pass(root, journal, drive)
        except Exception as exc:
            LOG.warning('drive_unavailable error_type=%s', type(exc).__name__)
            drive = None
        STOP.wait(30)


def main():
    os.umask(0o077)
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    if os.environ.get('RECORDING_ENABLED') != 'true':
        raise SystemExit('Recording disabled; explicit rollout required')
    root = Path(os.environ['RECORDING_ROOT'])
    root.mkdir(parents=True, exist_ok=True)
    lock = open(root / 'worker.lock', 'a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: STOP.set())
    # The lock proves no previous capture is active on this disk.
    for session in root.glob('capture-*'):
        if session.is_dir():
            publish(session, root, final=True)
    twitch = Twitch(os.environ['TWITCH_CLIENT_ID'], Path(os.environ['TWITCH_CLIENT_SECRET_FILE']).read_text().strip(),
                    os.environ['TWITCH_USER_ID'])
    if not twitch.user_id.isdigit():
        raise ValueError('TWITCH_USER_ID must be numeric')
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(uploader, root, os.environ['DRIVE_OAUTH_FILE'])
        try:
            while not STOP.is_set():
                if future.done():
                    future.result()
                    raise RuntimeError('Uploader stopped')
                try:
                    live = twitch.live()
                    if live:
                        if shutil.disk_usage(root).free < 3 * 1024**3:
                            LOG.error('capture_paused_low_disk')
                        else:
                            LOG.info('capture_start stream_id=%s', live['id'])
                            record(root, live['user_login'], live['id'])
                            LOG.info('capture_end stream_id=%s', live['id'])
                except Exception as exc:
                    LOG.warning('capture_retry error_type=%s', type(exc).__name__)
                STOP.wait(30)
        finally:
            STOP.set()


if __name__ == '__main__':
    main()
