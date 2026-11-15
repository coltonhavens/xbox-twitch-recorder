import copy
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
from recorder.worker import Drive, Video, CHUNK, FOLDER, CHANNEL, metadata, run, send_chunk, vod_info
from recorder.authorize_drive import persist


class Response:
    def __init__(self, status, headers=None, data=None):
        self.status_code, self.headers, self.data = status, headers or {}, data
    def json(self):
        return self.data


class Session:
    def __init__(self):
        self.content = bytearray()
        self.calls = []
    def patch(self, *args, **kwargs):
        return Response(200, {'Location': 'https://www.googleapis.com/upload/test-session'})
    def put(self, url, data, headers, timeout, **kwargs):
        self.calls.append((bytes(data), dict(headers)))
        self.content.extend(data)
        if headers['Content-Range'].endswith('/*'):
            return Response(308, {'Range': f'bytes=0-{len(self.content)-1}'})
        return Response(200, data={'id': 'stable-id'})


class Reader(io.BytesIO):
    def __init__(self, content, valid=True):
        super().__init__(content)
        self.valid, self.finished = valid, False
    def finish(self):
        self.finished = True
        if not self.valid:
            raise ValueError('Truncated source')


def drive_fake(session=None):
    drive = Drive.__new__(Drive)
    drive.data = {'version': 1, 'channel': CHANNEL, 'videos': {}}
    drive.session = session or Session()
    drive.saved = []
    drive.save = lambda: drive.saved.append(copy.deepcopy(drive.data))
    drive.remote = lambda file_id: {'id': file_id, 'parents': [FOLDER], 'appProperties': {
        'twitch_vod_id': '2917078189', 'twitch_channel': CHANNEL}, 'size': len(drive.session.content),
        'md5Checksum': hashlib.md5(drive.session.content).hexdigest()}
    return drive


class ArchiveTests(unittest.TestCase):
    def test_multichunk_full_content_hash_and_durable_expected_values(self):
        drive = drive_fake()
        entry = {'file_id': 'stable-id'}
        drive.data['videos']['2917078189'] = entry
        reader = Reader(b'full-video-and-audio')
        with patch('recorder.worker.CHUNK', 4):
            drive.stream({'id': '2917078189'}, entry, reader)
        self.assertEqual(drive.session.content, b'full-video-and-audio')
        self.assertTrue(reader.finished)
        self.assertTrue(entry['done'])
        self.assertNotIn('done', drive.saved[0]['videos']['2917078189'])
        self.assertEqual(drive.saved[0]['videos']['2917078189']['expected_md5'], hashlib.md5(b'full-video-and-audio').hexdigest())
        self.assertEqual(CHUNK % (256 * 1024), 0)

    def test_truncation_never_sends_final_chunk_or_marks_done(self):
        drive = drive_fake()
        entry = {'file_id': 'stable-id'}
        with patch('recorder.worker.CHUNK', 4), self.assertRaises(ValueError):
            drive.stream({'id': '2917078189'}, entry, Reader(b'abcdef', valid=False))
        self.assertEqual(drive.session.content, b'abcd')
        self.assertFalse(entry.get('done'))
        self.assertFalse(drive.saved)

    def test_ambiguous_final_success_reconciles_same_id_without_reupload(self):
        drive = drive_fake()
        entry = {'file_id': 'stable-id', 'expected_size': 3, 'expected_md5': hashlib.md5(b'abc').hexdigest()}
        drive.data['videos']['2917078189'] = entry
        drive.session.content.extend(b'abc')
        self.assertFalse(drive.prepare(entry, '2917078189'))
        self.assertTrue(entry['done'])
        self.assertEqual(drive.session.calls, [])

    def test_allocate_persists_id_before_create_is_possible(self):
        drive = drive_fake()
        drive.api = Mock()
        drive.api.files.return_value.generateIds.return_value.execute.return_value = {'ids': ['stable-id']}
        entry = drive.allocate('2917078189')
        self.assertEqual(drive.saved[-1]['videos']['2917078189']['file_id'], entry['file_id'])
        drive.api.files.return_value.create.assert_not_called()
        drive.allocate('2917078189')
        self.assertEqual(len(drive.saved), 1)

    def test_completed_file_conflict_is_never_overwritten(self):
        drive = drive_fake()
        entry = {'file_id': 'stable-id', 'done': True, 'expected_size': 50, 'expected_md5': 'wrong'}
        with self.assertRaises(ValueError):
            drive.prepare(entry, '2917078189')

    def test_partial_chunk_acknowledgement_only_retries_remaining_bytes(self):
        session = Mock()
        session.put.side_effect = [Response(308, {'Range':'bytes=0-1'}), Response(308, {'Range':'bytes=0-3'})]
        send_chunk(session, 'https://www.googleapis.com/upload/test', b'abcd', 0, sleep=lambda _:None)
        self.assertEqual(session.put.call_args_list[1].kwargs['data'], b'cd')

    def test_timeout_queries_status_before_resending(self):
        from requests.exceptions import Timeout
        session = Mock()
        session.put.side_effect = [Timeout(), Response(308, {'Range':'bytes=0-3'})]
        send_chunk(session, 'https://www.googleapis.com/upload/test', b'abcd', 0, sleep=lambda _:None)
        self.assertEqual(session.put.call_count, 2)
        self.assertEqual(session.put.call_args.kwargs['headers']['Content-Range'], 'bytes */*')

    def test_final_timeout_can_be_confirmed_by_status_query(self):
        from requests.exceptions import Timeout
        session = Mock()
        session.put.side_effect = [Timeout(), Response(200, data={'id':'same'})]
        self.assertEqual(send_chunk(session, 'https://www.googleapis.com/upload/test', b'final', 0, 5, sleep=lambda _:None), {'id':'same'})

    def test_bad_server_offsets_abort_instead_of_corrupting_media(self):
        session = Mock()
        session.put.return_value = Response(308, {'Range':'bytes=0-99'})
        with self.assertRaises(ValueError):
            send_chunk(session, 'https://www.googleapis.com/upload/test', b'abcd', 0, sleep=lambda _:None)

    def test_completion_requires_explicit_endlist(self):
        info = {'id':'v2917078189','uploader_id':CHANNEL,'duration':10,'is_live':False}
        with patch('recorder.worker.vod_info', return_value=info), self.assertRaises(ValueError):
            metadata('2917078189')
        info['completed_playlist'] = True
        with patch('recorder.worker.vod_info', return_value=info):
            self.assertEqual(metadata('2917078189')['id'], '2917078189')

    def test_playlist_checked_without_returning_signed_url(self):
        info = {'id':'v2917078189','uploader_id':CHANNEL,'duration':10,'is_live':False,
                'url':'https://example.invalid/secret-playback.m3u8'}
        response = Mock()
        response.__enter__ = lambda x: x
        response.__exit__ = lambda *x: None
        response.read.return_value = b'#EXTM3U\n#EXT-X-ENDLIST\n'
        with patch('recorder.worker.subprocess.run') as command, patch('recorder.worker.urllib.request.urlopen', return_value=response):
            command.return_value.stdout = json.dumps(info)
            result = vod_info('2917078189')
        self.assertTrue(result['completed_playlist'])
        self.assertNotIn('url', result)

    def test_drive_secret_file_private_and_never_overwritten(self):
        with tempfile.TemporaryDirectory() as scratch:
            output = Path(scratch) / 'secret.json'
            persist({'oauth': {'refresh_token':'fake'}}, output, False)
            self.assertEqual(output.stat().st_mode & 0o777, 0o600)
            with self.assertRaises(FileExistsError):
                persist({}, output, False)

    def test_github_secret_is_stdin_only_and_does_not_enable_workflow(self):
        with patch('recorder.authorize_drive.subprocess.run') as command:
            command.return_value.returncode = 0
            persist({'oauth':{'refresh_token':'fake-secret'}}, None, True)
        self.assertNotIn('fake-secret', ' '.join(command.call_args.args[0]))
        self.assertIn(b'fake-secret', command.call_args.kwargs['input'])
        self.assertIn('secret', command.call_args.args[0])
        self.assertNotIn('variable', command.call_args.args[0])

    def test_stable_duration_requires_another_scan_before_download(self):
        drive = drive_fake()
        video = {'id':'2917078189','duration':'10s'}
        with patch('recorder.worker.metadata', return_value=video), patch('recorder.worker.Video') as source:
            run(drive, ['2917078189'], now=lambda:1000)
            run(drive, ['2917078189'], now=lambda:1500)
            source.assert_not_called()
        self.assertEqual(drive.data['videos']['2917078189']['stable_since'], 1000)

    def test_expensive_attempt_limit_does_not_redownload(self):
        drive = drive_fake()
        drive.data['videos']['2917078189'] = {'attempts':5}
        with patch('recorder.worker.metadata') as extract:
            run(drive, ['2917078189'])
            extract.assert_not_called()

    def test_real_ffmpeg_stream_is_one_full_mp4_with_audio_and_temp_cleanup(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            fixture = root / 'source.ts'
            subprocess.run(['ffmpeg','-v','error','-f','lavfi','-i','testsrc=size=160x90:rate=10',
                '-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','8','-c:v','libx264',
                '-threads','1','-pix_fmt','yuv420p','-c:a','aac','-f','mpegts',str(fixture)], check=True, timeout=30)
            drive = drive_fake()
            entry = {'file_id':'stable-id'}
            drive.data['videos']['2917078189'] = entry
            with patch('recorder.worker.downloader_args', return_value=['cat',str(fixture)]):
                with Video({'id':'2917078189','duration':'8s'}) as reader:
                    temp = Path(reader.tmp.name)
                    drive.stream({'id':'2917078189'}, entry, reader)
                self.assertFalse(temp.exists())
            output = root / 'full.mp4'
            output.write_bytes(drive.session.content)
            result = subprocess.run(['ffprobe','-v','error','-show_entries','stream=codec_type:format=duration',
                '-of','json',str(output)], capture_output=True, check=True, timeout=30)
            probe = json.loads(result.stdout)
            self.assertEqual({s['codec_type'] for s in probe['streams']}, {'video','audio'})
            self.assertAlmostEqual(float(probe['format']['duration']), 8, delta=.5)
            self.assertTrue(entry['done'])

    def test_workflow_is_read_only_gated_and_has_no_paid_runner_or_media_artifact(self):
        source = Path('.github/workflows/archive-vods.yml').read_text()
        self.assertIn("vars.XTR_ARCHIVE_ENABLED == 'true'", source)
        self.assertIn('contents: read', source)
        self.assertIn('timeout-minutes: 330', source)
        self.assertIn('ubuntu-24.04', source)
        self.assertIn('github.event.repository.private == false', source)
        self.assertNotIn('upload-artifact@', source)
        self.assertNotIn('cache:', source)
        self.assertNotIn('id-token: write', source)

    def test_authorization_url_uses_pkce_state_and_does_not_expose_client_secret(self):
        from google_auth_oauthlib.flow import Flow
        import urllib.parse
        config = {'web':{'client_id':'test-client','client_secret':'never-public',
            'auth_uri':'https://accounts.google.com/o/oauth2/auth','token_uri':'https://oauth2.googleapis.com/token',
            'redirect_uris':['http://localhost:8765/callback']}}
        flow = Flow.from_client_config(config, scopes=['https://www.googleapis.com/auth/drive.file'],
            redirect_uri='http://localhost:8765/callback', autogenerate_code_verifier=True)
        url, state = flow.authorization_url(access_type='offline', prompt='consent')
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
        self.assertEqual(query['code_challenge_method'], ['S256'])
        self.assertEqual(query['state'], [state])
        self.assertNotIn('never-public', url)
        self.assertNotIn(flow.code_verifier, url)

    def test_unfinished_video_is_deferred_without_starting_download(self):
        from recorder.worker import NotReady
        drive = drive_fake()
        with patch('recorder.worker.metadata', side_effect=NotReady()), patch('recorder.worker.Video') as source:
            run(drive, ['2917078189'])
            source.assert_not_called()

    def test_untrusted_session_location_never_receives_oauth_or_media(self):
        drive = drive_fake()
        drive.session = Mock()
        drive.session.patch.return_value = Response(200, {'Location':'https://evil.invalid/upload'})
        with self.assertRaises(RuntimeError):
            drive.stream({'id':'2917078189'}, {'file_id':'stable-id'}, Reader(b'private'))
        drive.session.put.assert_not_called()
