"""Scheduled, bounded-memory completed-VOD archive. No live recorder or provisioning."""
import argparse
import datetime as dt
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

LOG = logging.getLogger('vod-archive')
CHANNEL = 'mrhype420'
FOLDER = '1X9VfSes_byvkygreHfdvGNHzVXjvAYBG'
CHUNK = 8 * 1024 * 1024
LEASE_SECONDS = 7 * 3600  # Must exceed Cloud Run's approved six-hour task timeout.


def seconds(value):
    match = re.fullmatch(r'(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?', value)
    if not match or not any(match.groups()):
        raise ValueError('Invalid Twitch duration')
    return sum(int(n or 0) * unit for n, unit in zip(match.groups(), (3600, 60, 1)))


def instant(value):
    return dt.datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def observe(state, video, now, offline, since):
    """Fail closed: two stable duration observations >=10min apart, owner offline."""
    if (video['user_login'].lower() != CHANNEL or video['type'] != 'archive' or
            instant(video['created_at']) < since):
        return False
    duration = seconds(video['duration'])
    if duration <= 0:
        return False
    if state.get('observed_duration') != duration:
        state.update(observed_duration=duration, stable_since=now)
        return False
    return offline and now - state['stable_since'] >= 600


def validate_info(info, video):
    if (str(info.get('id', '')).lstrip('v') != video['id'] or
            str(info.get('uploader_id', '')).lower() != CHANNEL or
            info.get('is_live') is not False):
        raise ValueError('VOD identity or completion unverified')
    expected = seconds(video['duration'])
    if abs(float(info.get('duration') or 0) - expected) > 2:
        raise ValueError('VOD duration changed; wait for next scan')


def downloader_args(vod_id):
    if not re.fullmatch(r'\d+', vod_id):
        raise ValueError('Invalid VOD ID')
    return ['yt-dlp', '--ignore-config', '--no-playlist', '--no-progress', '--quiet',
            '--socket-timeout', '30', '--retries', '5', '--fragment-retries', '5',
            '--abort-on-unavailable-fragments', '--hls-use-mpegts', '--downloader', 'native',
            '-f', 'best[vcodec!=none][acodec!=none]', '-o', '-',
            'https://www.twitch.tv/videos/' + vod_id]


def vod_info(vod_id):
    args = downloader_args(vod_id)
    result = subprocess.run(args[:-3] + ['--skip-download', '--dump-single-json', args[-1]],
                            capture_output=True, timeout=180, check=True)
    # Full extractor JSON may contain signed playback URLs: never log/save it.
    info = json.loads(result.stdout)
    return {key: info.get(key) for key in ('id', 'uploader_id', 'duration', 'is_live')}


def mux_args(progress):
    return ['ffmpeg', '-nostdin', '-v', 'error', '-xerror', '-i', 'pipe:0',
            '-map', '0:v:0', '-map', '0:a:0', '-c', 'copy', '-bsf:a', 'aac_adtstoasc',
            '-movflags', 'frag_keyframe+empty_moov+default_base_moof',
            '-progress', str(progress), '-f', 'mp4', 'pipe:1']


def validate_progress(text, expected):
    times = [int(line.split('=', 1)[1]) / 1_000_000 for line in text.splitlines()
             if line.startswith('out_time_us=') and line.split('=', 1)[1].lstrip('-').isdigit()]
    duration = max(times, default=0)
    # Absolute tolerance, not a percentage that could silently lose minutes on a long VOD.
    if duration <= 0 or 'progress=end' not in text or abs(duration - expected) > min(5, max(0.5, expected * 0.001)):
        raise ValueError('Incomplete media duration')
    return duration


def stop(process):
    if process and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


def stage_video(video, sink):
    """Remux full VOD to one fragmented MP4; stream to seek-free GCS sink."""
    source = target = None
    md5 = hashlib.md5()
    size = 0
    with tempfile.TemporaryDirectory() as scratch:
        progress = Path(scratch) / 'progress'
        try:
            source = subprocess.Popen(downloader_args(video['id']), stdout=subprocess.PIPE,
                                      stderr=subprocess.DEVNULL)
            target = subprocess.Popen(mux_args(progress), stdin=source.stdout,
                                      stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            source.stdout.close()
            while block := target.stdout.read(CHUNK):
                sink.write(block)
                md5.update(block)
                size += len(block)
            if target.wait(timeout=60) != 0 or source.wait(timeout=60) != 0:
                raise RuntimeError('Downloader/remux failed; stage must not be uploaded')
            duration = validate_progress(progress.read_text(), seconds(video['duration']))
            if not size:
                raise ValueError('Empty VOD')
            return {'size': size, 'md5': md5.hexdigest(), 'duration': duration}
        finally:
            stop(source)
            stop(target)
            if target and target.stdout:
                target.stdout.close()


class Twitch:
    def __init__(self, client_id, secret):
        body = urllib.parse.urlencode({'client_id': client_id, 'client_secret': secret,
                                       'grant_type': 'client_credentials'}).encode()
        with urllib.request.urlopen(urllib.request.Request('https://id.twitch.tv/oauth2/token', data=body), timeout=30) as r:
            self.token = json.load(r)['access_token']
        self.client_id = client_id

    def get(self, resource, **query):
        req = urllib.request.Request('https://api.twitch.tv/helix/' + resource + '?' + urllib.parse.urlencode(query),
                                     headers={'Client-ID': self.client_id, 'Authorization': 'Bearer ' + self.token})
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)

    def scan(self):
        users = self.get('users', login=CHANNEL)['data']
        if len(users) != 1 or users[0]['login'].lower() != CHANNEL:
            raise ValueError('Cannot resolve channel identity')
        user_id = users[0]['id']
        offline = not self.get('streams', user_id=user_id)['data']
        videos, cursor = [], None
        for _ in range(100):
            args = {'user_id': user_id, 'type': 'archive', 'first': 100}
            if cursor:
                args['after'] = cursor
            page = self.get('videos', **args)
            videos.extend(page['data'])
            cursor = page.get('pagination', {}).get('cursor')
            if not cursor:
                return offline, videos
        raise RuntimeError('Pagination cap exceeded; refuse incomplete scan')


class Bucket:
    def __init__(self, name):
        from google.cloud import storage
        self.bucket = storage.Client().bucket(name)
        self.owner = uuid.uuid4().hex
        self.lock_generation = None
        self.deadline = 0

    def read(self, key):
        from google.api_core.exceptions import NotFound
        try:
            return json.loads(self.bucket.blob('state/' + key + '.json').download_as_text())
        except NotFound:
            return {}

    def save(self, key, data):
        self.assert_lease()
        self.bucket.blob('state/' + key + '.json').upload_from_string(json.dumps(data), content_type='application/json')

    def acquire(self, now):
        from google.api_core.exceptions import NotFound, PreconditionFailed
        blob = self.bucket.blob('state/lock.json')
        try:
            # Bind bytes to the generation being replaced, never a second unpinned GET.
            blob.reload()
            generation = blob.generation
            old = json.loads(blob.download_as_text(if_generation_match=generation))
            if old.get('until', 0) > now:
                return False
        except NotFound:
            generation = 0
        except PreconditionFailed:
            return False
        self.deadline = now + LEASE_SECONDS
        try:
            blob.upload_from_string(json.dumps({'owner': self.owner, 'until': self.deadline}),
                                    if_generation_match=generation, content_type='application/json')
        except PreconditionFailed:
            return False
        self.lock_generation = blob.generation
        return True

    def assert_lease(self):
        if not self.lock_generation or time.time() >= self.deadline - 180:
            raise RuntimeError('Lease expired; stop before further side effects')

    def release(self):
        if self.lock_generation:
            self.bucket.blob('state/lock.json').delete(if_generation_match=self.lock_generation)

    def stage(self, video):
        self.assert_lease()
        blob = self.bucket.blob('staging/' + video['id'] + '.mp4')
        with blob.open('wb', chunk_size=CHUNK, ignore_flush=True) as sink:
            metadata = stage_video(video, sink)
        blob.reload()
        metadata['generation'] = int(blob.generation)
        return metadata

    def open_stage(self, vod_id, generation):
        blob = self.bucket.blob('staging/' + vod_id + '.mp4', generation=generation)
        blob.reload()
        return blob.open('rb', chunk_size=CHUNK)

    def cleanup(self, vod_id, generation):
        from google.api_core.exceptions import NotFound
        if generation:
            self.assert_lease()
            try:
                self.bucket.blob('staging/' + vod_id + '.mp4').delete(if_generation_match=generation)
            except NotFound:
                pass  # Crash after successful cleanup must be idempotent.


class Drive:
    def __init__(self, path):
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build
        from google_auth_httplib2 import AuthorizedHttp
        import httplib2
        credentials = Credentials.from_authorized_user_file(path)
        if set(credentials.scopes or []) != {'https://www.googleapis.com/auth/drive.file'}:
            raise ValueError('Require owner-authorized drive.file, no broader scope')
        self.api = build('drive', 'v3', http=AuthorizedHttp(credentials, http=httplib2.Http(timeout=120)), cache_discovery=False)
        folder = self.api.files().get(fileId=FOLDER, fields='mimeType,capabilities(canAddChildren)', supportsAllDrives=True).execute(num_retries=3)
        if folder['mimeType'] != 'application/vnd.google-apps.folder' or not folder.get('capabilities', {}).get('canAddChildren'):
            raise ValueError('Drive folder is not authorized for this app')

    def allocate(self):
        return self.api.files().generateIds(count=1, space='drive', type='files').execute(num_retries=3)['ids'][0]

    def existing(self, file_id):
        from googleapiclient.errors import HttpError
        try:
            return self.api.files().get(fileId=file_id, fields='id,size,md5Checksum,parents,appProperties,trashed', supportsAllDrives=True).execute(num_retries=3)
        except HttpError as exc:
            if exc.resp.status == 404:
                return None
            raise

    @staticmethod
    def verify(remote, video, media):
        if (remote.get('trashed') or FOLDER not in remote.get('parents', []) or
                remote.get('appProperties', {}).get('twitch_vod_id') != video['id'] or
                remote.get('appProperties', {}).get('twitch_channel') != CHANNEL or
                int(remote.get('size', -1)) != media['size'] or remote.get('md5Checksum') != media['md5']):
            raise ValueError('Remote verification failed; preserve stage/state')

    def upload(self, reader, file_id, video, checkpoint):
        from googleapiclient.http import MediaIoBaseUpload
        media = MediaIoBaseUpload(reader, mimetype='video/mp4', chunksize=CHUNK, resumable=True)
        request = self.api.files().create(body={'id': file_id, 'name': 'MrHype420-' + video['id'] + '.mp4',
                                               'parents': [FOLDER], 'appProperties': {'twitch_vod_id': video['id'], 'twitch_channel': CHANNEL}},
                                           media_body=media, fields='id,size,md5Checksum,parents,appProperties,trashed', supportsAllDrives=True)
        result = None
        while result is None:
            checkpoint()
            _, result = request.next_chunk(num_retries=5)
        return result


def archive(video, state, store, drive):
    """Stable ID persisted before create: retries and ambiguous success cannot duplicate."""
    if state.get('done'):
        if state.get('media', {}).get('generation'):
            store.cleanup(video['id'], state['media']['generation'])
            state['media']['generation'] = None
            store.save(video['id'], state)
        return
    if not state.get('drive_id'):
        state['drive_id'] = drive.allocate()
        store.save(video['id'], state)
    remote = drive.existing(state['drive_id'])
    if remote is not None:
        if not state.get('media'):
            raise ValueError('Remote exists without expected checksum; manual review')
        drive.verify(remote, video, state['media'])
    else:
        if not state.get('media'):
            validate_info(vod_info(video['id']), video)
            state['media'] = store.stage(video)
            store.save(video['id'], state)  # Checksum + generation BEFORE Drive side effect.
        with store.open_stage(video['id'], state['media']['generation']) as reader:
            remote = drive.upload(reader, state['drive_id'], video, store.assert_lease)
        drive.verify(remote, video, state['media'])
    state.update(done=True, completed_at=time.time())
    store.save(video['id'], state)  # Durable completion BEFORE deleting staging media.
    store.cleanup(video['id'], state['media']['generation'])
    state['media']['generation'] = None
    store.save(video['id'], state)
    LOG.info('vod_archived id=%s drive_id=%s', video['id'], state['drive_id'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--vod-id', help='Limit discovery to one owned archived VOD; no completion bypass')
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    if os.environ.get('ARCHIVE_ENABLED') != 'true':
        raise SystemExit('Archive disabled; explicit rollout approval required')
    since = instant(os.environ['ARCHIVE_SINCE'])
    store = Bucket(os.environ['STATE_BUCKET'])
    if not store.acquire(time.time()):
        LOG.info('overlapping_job_skipped')
        return
    errors = 0
    try:
        twitch = Twitch(os.environ['TWITCH_CLIENT_ID'], Path(os.environ['TWITCH_CLIENT_SECRET_FILE']).read_text().strip())
        offline, videos = twitch.scan()
        drive = None
        for video in sorted(videos, key=lambda v: v['created_at']):
            if args.vod_id and video['id'] != args.vod_id:
                continue
            store.assert_lease()
            state = store.read(video['id'])
            if state.get('done') and not state.get('media', {}).get('generation'):
                continue
            try:
                if not state.get('done') and not state.get('media'):
                    eligible = observe(state, video, time.time(), offline, since)
                    store.save(video['id'], state)
                    if not eligible:
                        continue
                if drive is None:
                    drive = Drive(os.environ['DRIVE_OAUTH_FILE'])
                archive(video, state, store, drive)
            except Exception as exc:
                errors += 1
                LOG.error('vod_pending id=%s error_type=%s', video['id'], type(exc).__name__)
        if errors:
            raise RuntimeError('Pending VOD failures; inspect logs and retry next schedule')
    finally:
        store.release()


if __name__ == '__main__':
    main()
