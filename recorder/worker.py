"""GitHub Actions VOD archiver: full MP4 streamed to owner Drive, no cloud infrastructure."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import tempfile
import time
import urllib.request
import urllib.parse

CHANNEL = 'mrhype420'
FOLDER = '1X9VfSes_byvkygreHfdvGNHzVXjvAYBG'
CHUNK = 8 * 1024 * 1024
MAX_BYTES = 100 * 1024 ** 3

def seconds(value):
    match = re.fullmatch(r'(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?', value)
    if not match or not any(match.groups()):
        raise ValueError('Invalid Twitch duration')
    return sum(int(n or 0) * unit for n, unit in zip(match.groups(), (3600, 60, 1)))


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
    result = {key: info.get(key) for key in ('id', 'uploader_id', 'duration', 'is_live')}
    url = info.get('url', '')
    if not url.startswith('https://'):
        raise ValueError('No secure selected media playlist')
    request = urllib.request.Request(url, headers=info.get('http_headers', {}))
    with urllib.request.urlopen(request, timeout=30) as response:
        playlist = response.read(8 * 1024 * 1024 + 1)
    if len(playlist) > 8 * 1024 * 1024:
        raise ValueError('Unexpected playlist size')
    result['completed_playlist'] = b'#EXT-X-ENDLIST' in playlist.splitlines()
    return result


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



class NotReady(ValueError):
    pass


def metadata(vod_id):
    info = vod_info(vod_id)
    if (str(info.get('uploader_id', '')).lower() != CHANNEL or
            str(info.get('id', '')).lstrip('v') != vod_id):
        raise ValueError('Unverified owner/identity')
    if info.get('is_live') is not False or not info.get('completed_playlist') or not info.get('duration'):
        raise NotReady('VOD is live or still processing')
    return {'id': vod_id, 'duration': f"{int(info['duration'])}s", 'user_login': CHANNEL, 'type': 'archive'}


def discover():
    # yt-dlp paginates Twitch's ARCHIVE playlist; no extra owner Twitch API secret.
    result = subprocess.run(['yt-dlp', '--ignore-config', '--quiet', '--flat-playlist', '--dump-single-json',
                             '--socket-timeout', '30', '--playlist-end', '501',
                             'https://www.twitch.tv/' + CHANNEL + '/videos?filter=archives&sort=time'],
                            capture_output=True, check=True, timeout=240)
    entries = json.loads(result.stdout).get('entries', [])
    if not entries:
        raise ValueError('Empty ARCHIVE playlist; verify downloader compatibility')
    if len(entries) > 500:
        raise ValueError('Discovery cap exceeded; review rather than omit videos')
    ids = []
    for entry in entries:
        vod_id = str(entry['id']).lstrip('v')
        if not vod_id.isdigit():
            raise ValueError('Unexpected playlist identity')
        ids.append(vod_id)
    return list(dict.fromkeys(ids))


class Video:
    def __init__(self, video):
        self.video = video
        self.tmp = tempfile.TemporaryDirectory(prefix='xtr-')
        self.progress = Path(self.tmp.name) / 'progress'
        self.source = self.target = None

    def __enter__(self):
        try:
            self.source = subprocess.Popen(downloader_args(self.video['id']), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            self.target = subprocess.Popen(mux_args(self.progress), stdin=self.source.stdout, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            self.source.stdout.close()
            return self
        except BaseException:
            self.__exit__(None, None, None)
            raise

    def read(self, size):
        return self.target.stdout.read(size)

    def finish(self):
        if self.target.wait(timeout=60) != 0 or self.source.wait(timeout=60) != 0:
            raise RuntimeError('Download/remux failed; incomplete media must not commit')
        return validate_progress(self.progress.read_text(), seconds(self.video['duration']))

    def __exit__(self, *_):
        for process in (self.source, self.target):
            if process is not None and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
        if self.target and self.target.stdout:
            self.target.stdout.close()
        self.tmp.cleanup()


def ack_offset(response):
    header = response.headers.get('Range', '')
    if not header:
        return 0
    match = re.fullmatch(r'bytes=0-(\d+)', header)
    if not match:
        raise ValueError('Invalid Drive acknowledgement')
    return int(match.group(1)) + 1


def send_chunk(session, url, block, start, total=None, sleep=time.sleep):
    """Retry/status-query ambiguous sends using only the retained current chunk."""
    from requests.exceptions import RequestException
    end = start + len(block)
    position = start
    for attempt in range(6):
        try:
            response = session.put(url, data=block[position-start:], headers={
                'Content-Length': str(end-position),
                'Content-Range': f"bytes {position}-{end-1}/{total if total is not None else '*'}"}, timeout=120, allow_redirects=False)
            if response.status_code in (200, 201):
                if total is None:
                    raise ValueError('Drive prematurely completed upload')
                return response.json()
            if response.status_code == 308:
                confirmed = ack_offset(response)
            elif response.status_code in (408, 429) or response.status_code >= 500:
                raise RequestException('Retryable Drive status')
            else:
                raise RuntimeError('Drive upload rejected')
        except RequestException:
            try:
                response = session.put(url, data=b'', headers={'Content-Length': '0',
                    'Content-Range': f"bytes */{total if total is not None else '*'}"}, timeout=120, allow_redirects=False)
            except RequestException:
                sleep(min(2 ** attempt, 32))
                continue
            if response.status_code in (200, 201):
                if total is None:
                    raise ValueError('Unexpected early completion')
                return response.json()
            if response.status_code != 308:
                if response.status_code in (408, 429) or response.status_code >= 500:
                    sleep(min(2 ** attempt, 32))
                    continue
                raise RuntimeError('Drive session expired; retry full VOD next run')
            confirmed = ack_offset(response)
        if not start <= confirmed <= end:
            raise ValueError('Drive offset outside retained chunk; restart next run')
        if confirmed == end:
            if total is not None:
                # Final 308 is not proof of completed object. Next run can reconcile.
                raise RuntimeError('Final upload not confirmed')
            return None
        position = confirmed
        sleep(min(2 ** attempt, 32))
    raise TimeoutError('Drive chunk retry allowance exhausted')


class Drive:
    def __init__(self, config):
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import AuthorizedSession
        from googleapiclient.discovery import build
        from google_auth_httplib2 import AuthorizedHttp
        import httplib2
        oauth = config['oauth']
        if set(oauth.get('scopes', [])) != {'https://www.googleapis.com/auth/drive.file'}:
            raise ValueError('Require exactly owner drive.file authorization')
        credentials = Credentials.from_authorized_user_info(oauth)
        self.session = AuthorizedSession(credentials)
        self.api = build('drive', 'v3', http=AuthorizedHttp(credentials, http=httplib2.Http(timeout=120)), cache_discovery=False)
        self.manifest_id = config['manifest_id']
        folder = self.api.files().get(fileId=FOLDER, fields='id,mimeType,capabilities(canAddChildren)').execute(num_retries=3)
        if folder['mimeType'] != 'application/vnd.google-apps.folder' or not folder.get('capabilities', {}).get('canAddChildren'):
            raise ValueError('Existing folder not authorized')
        meta = self.api.files().get(fileId=self.manifest_id, fields='parents,appProperties,trashed').execute(num_retries=3)
        if meta.get('trashed') or FOLDER not in meta.get('parents', []) or meta.get('appProperties', {}).get('xtr_role') != 'manifest':
            raise ValueError('Invalid private recovery manifest')
        self.data = json.loads(self.api.files().get_media(fileId=self.manifest_id).execute(num_retries=3))
        if self.data.get('version') != 1 or self.data.get('channel') != CHANNEL or not isinstance(self.data.get('videos'), dict):
            raise ValueError('Invalid recovery data; do not silently reset it')

    def save(self):
        from googleapiclient.http import MediaIoBaseUpload
        import io
        content = json.dumps(self.data, sort_keys=True).encode()
        self.api.files().update(fileId=self.manifest_id, media_body=MediaIoBaseUpload(io.BytesIO(content), mimetype='application/json')).execute(num_retries=3)

    def allocate(self, vod_id):
        entry = self.data['videos'].setdefault(vod_id, {})
        if not entry.get('file_id'):
            entry['file_id'] = self.api.files().generateIds(count=1, space='drive', type='files').execute(num_retries=3)['ids'][0]
            self.save()  # Durable on Drive BEFORE any archive file create.
        return entry

    def remote(self, file_id):
        from googleapiclient.errors import HttpError
        try:
            return self.api.files().get(fileId=file_id, fields='id,size,md5Checksum,parents,appProperties,trashed').execute(num_retries=3)
        except HttpError as exc:
            if exc.resp.status == 404:
                return None
            raise

    @staticmethod
    def verified(remote, entry, vod_id):
        return bool(remote and not remote.get('trashed') and FOLDER in remote.get('parents', []) and
                    remote.get('appProperties', {}).get('twitch_vod_id') == vod_id and
                    remote.get('appProperties', {}).get('twitch_channel') == CHANNEL and
                    entry.get('expected_size', 0) > 0 and
                    int(remote.get('size', -1)) == entry.get('expected_size') and
                    remote.get('md5Checksum') == entry.get('expected_md5'))

    def prepare(self, entry, vod_id):
        remote = self.remote(entry['file_id'])
        if self.verified(remote, entry, vod_id):
            entry['done'] = True
            self.save()
            return False
        if entry.get('done'):
            raise ValueError('Previously completed archive changed/deleted; manual review')
        if remote is None:
            self.api.files().create(body={'id': entry['file_id'], 'name': 'MrHype420-' + vod_id + '.mp4',
                'parents': [FOLDER], 'mimeType': 'video/mp4',
                'appProperties': {'twitch_vod_id': vod_id, 'twitch_channel': CHANNEL}}, fields='id').execute(num_retries=0)
        elif (FOLDER not in remote.get('parents', []) or remote.get('trashed') or
              remote.get('appProperties', {}).get('twitch_vod_id') != vod_id or
              remote.get('appProperties', {}).get('twitch_channel') != CHANNEL):
            raise ValueError('Archive ID conflict; do not overwrite')
        return True

    def stream(self, video, entry, reader):
        response = self.session.patch('https://www.googleapis.com/upload/drive/v3/files/' + entry['file_id'],
            params={'uploadType': 'resumable'}, json={}, headers={'X-Upload-Content-Type': 'video/mp4'}, timeout=120, allow_redirects=False)
        url = response.headers.get('Location', '')
        target = urllib.parse.urlsplit(url)
        if (response.status_code != 200 or target.scheme != 'https' or
                target.hostname not in ('www.googleapis.com', 'content.googleapis.com') or
                target.port not in (None, 443) or target.username is not None):
            raise RuntimeError('Cannot start trusted Drive upload')  # Bearer-like session URL: never log/persist it.
        block = reader.read(CHUNK)
        if not block:
            raise ValueError('Empty source')
        size, digest = 0, hashlib.md5()
        while block:
            following = reader.read(CHUNK)  # One-chunk lookahead, independent of full VOD size.
            size += len(block)
            if size > MAX_BYTES:
                raise ValueError('100 GiB safety limit exceeded')
            digest.update(block)
            final = not following
            if final:
                reader.finish()  # Both processes + expected duration BEFORE final commit.
                entry.update(expected_size=size, expected_md5=digest.hexdigest())
                self.save()  # Recover ambiguous final success on the next run.
            send_chunk(self.session, url, block, size-len(block), size if final else None)
            block = following
        remote = self.remote(entry['file_id'])
        if not self.verified(remote, entry, video['id']):
            raise ValueError('Final checksum/parent/identity verification failed')
        entry['done'] = True
        self.save()


def run(drive, ids, now=time.time):
    errors = 0
    for vod_id in ids:
        entry = drive.data['videos'].get(vod_id, {})
        try:
            # Always reconcile prior success before spending a retry or querying Twitch.
            if entry.get('file_id') and not drive.prepare(entry, vod_id):
                continue
            if entry.get('attempts', 0) >= 5 or now() < entry.get('retry_after', 0):
                continue
            video = metadata(vod_id)
            duration = seconds(video['duration'])
            if entry.get('duration') != duration:
                entry.update(duration=duration, stable_since=now())
                drive.data['videos'][vod_id] = entry
                drive.save()
                continue
            if now() - entry['stable_since'] < 600:
                continue
            entry = drive.allocate(vod_id)
            if not drive.prepare(entry, vod_id):
                continue
            entry.update(attempts=entry.get('attempts', 0)+1,
                         retry_after=now()+3600 * 2**entry.get('attempts', 0))
            drive.save()
            with Video(video) as reader:
                drive.stream(video, entry, reader)
            print(json.dumps({'vod_id': vod_id, 'verified': True}), flush=True)
        except NotReady:
            continue
        except Exception as exc:
            if isinstance(exc, RunDeadline):
                raise
            errors += 1
            # No extractor error strings: they can contain signed URLs or credentials.
            print(json.dumps({'vod_id': vod_id, 'error_type': type(exc).__name__}), flush=True)
    if errors:
        raise RuntimeError('Pending archive failures; next schedule retries within allowance')


class RunDeadline(TimeoutError):
    pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--vod-id')
    args = parser.parse_args()
    if os.environ.get('ARCHIVE_ENABLED') != 'true':
        raise SystemExit('Archive disabled')
    def expired(*_):
        raise RunDeadline('Five-hour processing allowance exhausted')
    signal.signal(signal.SIGALRM, expired)
    signal.alarm(18000)
    try:
        config = json.loads(os.environ.pop('XTR_DRIVE_AUTH'))
        drive = Drive(config)
        try:
            ids = [args.vod_id] if args.vod_id else discover()
        except ValueError:
            if not any(not v.get('done') for v in drive.data['videos'].values()):
                raise
            ids = []  # Still reconcile pending remote success if discovery is temporarily unavailable.
        if any(not re.fullmatch(r'\d+', item) for item in ids):
            raise ValueError('Invalid VOD ID')
        # Also reconcile unfinished IDs no longer listed by Twitch (e.g. expired VOD).
        ids = list(dict.fromkeys(ids + [key for key, v in drive.data['videos'].items() if not v.get('done')]))
        run(drive, ids)
    finally:
        signal.alarm(0)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print(json.dumps({'success': False, 'error_type': type(exc).__name__}))
        raise SystemExit(1)
