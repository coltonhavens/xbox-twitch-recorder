import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from recorder.worker import (CHANNEL, FOLDER, Drive, archive, downloader_args, mux_args,
                             observe, seconds, validate_info, validate_progress, vod_info)

VIDEO = {'id': '2917078189', 'user_login': 'MrHype420', 'type': 'archive',
         'created_at': '2026-11-01T00:00:00Z', 'duration': '1h2m3s'}
MEDIA = {'size': 100, 'md5': 'known-hash', 'generation': 1}


class Store:
    def __init__(self):
        self.saved = {}
        self.stage_calls = self.cleanups = 0
    def save(self, key, data):
        self.saved[key] = copy.deepcopy(data)
    def assert_lease(self):
        pass
    def stage(self, video):
        self.stage_calls += 1
        return dict(MEDIA)
    def open_stage(self, *args):
        return io.BytesIO(b'x' * 100)
    def cleanup(self, *args):
        self.cleanups += 1


class FakeDrive:
    def __init__(self):
        self.remote = None
        self.allocations = self.uploads = 0
        self.fail_after_create = False
    def allocate(self):
        self.allocations += 1
        return 'stable-id'
    def existing(self, file_id):
        return self.remote
    def upload(self, reader, file_id, video, checkpoint):
        checkpoint()
        self.uploads += 1
        self.remote = {'id': file_id, 'parents': [FOLDER], 'appProperties': {
            'twitch_vod_id': video['id'], 'twitch_channel': CHANNEL},
            'size': MEDIA['size'], 'md5Checksum': MEDIA['md5']}
        if self.fail_after_create:
            raise TimeoutError('Ambiguous remote success')
        return self.remote
    verify = staticmethod(Drive.verify)


class VodTests(unittest.TestCase):
    def test_parse_duration(self):
        self.assertEqual(seconds('1h2m3s'), 3723)
        self.assertEqual(seconds('42s'), 42)
        for bad in ('', 'banana', '2d', '-1s'):
            with self.assertRaises(ValueError):
                seconds(bad)

    def test_completion_requires_stable_observations_and_offline(self):
        state = {}
        self.assertFalse(observe(state, VIDEO, 1000, True, 0))
        self.assertFalse(observe(state, VIDEO, 1599, True, 0))
        self.assertFalse(observe(state, VIDEO, 1600, False, 0))
        self.assertTrue(observe(state, VIDEO, 1600, True, 0))
        self.assertFalse(observe(state, dict(VIDEO, duration='1h3m'), 1700, True, 0))

    def test_filters_other_owner_highlights_and_cutoff(self):
        for video in (dict(VIDEO, user_login='other'), dict(VIDEO, type='highlight')):
            self.assertFalse(observe({}, video, 1000, True, 0))
        self.assertFalse(observe({}, VIDEO, 1000, True, 9999999999))

    def test_extractor_identity_live_and_duration(self):
        info = {'id': 'v2917078189', 'uploader_id': 'mrhype420', 'duration': 3723, 'is_live': False}
        validate_info(info, VIDEO)
        for key, value in [('id', 'v123'), ('uploader_id', 'other'), ('is_live', None), ('is_live', True), ('duration', 3000)]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                validate_info(dict(info, **{key: value}), VIDEO)

    def test_downloader_is_strict_full_av_and_metadata_args_are_valid(self):
        args = downloader_args(VIDEO['id'])
        self.assertIn('--abort-on-unavailable-fragments', args)
        self.assertEqual(args[args.index('--downloader') + 1], 'native')
        self.assertIn('best[vcodec!=none][acodec!=none]', args)
        self.assertNotIn('--download-sections', args)
        with patch('recorder.worker.subprocess.run') as run:
            run.return_value.stdout = json.dumps({'id': 'v2917078189', 'uploader_id': CHANNEL, 'duration': 3723, 'is_live': False})
            vod_info(VIDEO['id'])
            metadata_args = run.call_args.args[0]
            self.assertNotIn('-o', metadata_args)
            self.assertIn('--dump-single-json', metadata_args)
        with self.assertRaises(ValueError):
            downloader_args('2917;bad')

    def test_duration_validation_rejects_truncation(self):
        validate_progress('out_time_us=3723000000\nprogress=end\n', 3723)
        for text in ('out_time_us=3000000000\nprogress=end\n', 'out_time_us=3723000000\n', 'progress=end\n'):
            with self.assertRaises(ValueError):
                validate_progress(text, 3723)

    @patch('recorder.worker.vod_info', return_value={'id': 'v2917078189', 'uploader_id': CHANNEL, 'duration': 3723, 'is_live': False})
    def test_ambiguous_upload_success_reuses_id_without_download_or_upload(self, _):
        state, store, drive = {}, Store(), FakeDrive()
        drive.fail_after_create = True
        with self.assertRaises(TimeoutError):
            archive(VIDEO, state, store, drive)
        restarted = copy.deepcopy(store.saved[VIDEO['id']])
        self.assertEqual(restarted['drive_id'], 'stable-id')
        self.assertIn('media', restarted)
        archive(VIDEO, restarted, store, drive)
        archive(VIDEO, restarted, store, drive)
        self.assertEqual((drive.allocations, drive.uploads, store.stage_calls), (1, 1, 1))
        self.assertTrue(store.saved[VIDEO['id']]['done'])
        self.assertEqual(store.cleanups, 1)

    def test_conflicting_remote_never_marked_complete_or_deleted(self):
        state, store, drive = {'drive_id': 'stable-id', 'media': dict(MEDIA)}, Store(), FakeDrive()
        drive.remote = {'id': 'stable-id', 'size': 99, 'parents': [FOLDER]}
        with self.assertRaises(ValueError):
            archive(VIDEO, state, store, drive)
        self.assertFalse(state.get('done'))
        self.assertEqual(store.cleanups, 0)

    def test_upload_failure_reuses_valid_stage(self):
        store, drive = Store(), FakeDrive()
        state = {'drive_id': 'stable-id', 'media': dict(MEDIA)}
        with patch.object(drive, 'upload', side_effect=TimeoutError()):
            with self.assertRaises(TimeoutError):
                archive(VIDEO, state, store, drive)
        archive(VIDEO, state, store, drive)
        self.assertEqual(store.stage_calls, 0)
        self.assertTrue(state['done'])

    def test_real_ffmpeg_produces_one_full_mp4_with_audio(self):
        with tempfile.TemporaryDirectory() as scratch:
            root = Path(scratch)
            fixture = root / 'input.ts'
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc=size=160x90:rate=10',
                            '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000', '-t', '8',
                            '-c:v', 'libx264', '-threads', '1', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
                            '-f', 'mpegts', str(fixture)], check=True, timeout=30)
            output = root / 'complete.mp4'
            with fixture.open('rb') as source, output.open('wb') as sink:
                subprocess.run(mux_args(root / 'progress'), stdin=source, stdout=sink, check=True, timeout=30)
            validate_progress((root / 'progress').read_text(), 8)
            result = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'stream=codec_type:format=duration',
                                     '-of', 'json', str(output)], check=True, capture_output=True, timeout=30)
            info = json.loads(result.stdout)
            self.assertEqual({s['codec_type'] for s in info['streams']}, {'video', 'audio'})
            self.assertAlmostEqual(float(info['format']['duration']), 8, delta=0.5)
            self.assertEqual(len(list(root.glob('*.mp4'))), 1)

    def test_last_ambiguous_attempt_can_reconcile_without_spending_another_attempt(self):
        state, store, drive = {'drive_id': 'stable-id', 'media': dict(MEDIA), 'attempts': 5}, Store(), FakeDrive()
        drive.remote = {'id': 'stable-id', 'parents': [FOLDER], 'appProperties': {
            'twitch_vod_id': VIDEO['id'], 'twitch_channel': CHANNEL}, 'size': 100, 'md5Checksum': 'known-hash'}
        from unittest.mock import Mock
        budget = Mock()
        budget.begin_attempt.side_effect = AssertionError('Reconciliation must not spend an attempt')
        archive(VIDEO, state, store, drive, budget)
        self.assertTrue(state['done'])
        self.assertEqual(drive.uploads, 0)

    def test_oversized_output_stops_before_writing_and_reaps_children(self):
        from unittest.mock import Mock
        from recorder.worker import stage_video
        from recorder.guards import GuardStop
        source, target = Mock(), Mock()
        source.poll.return_value = target.poll.return_value = 0
        target.stdout = io.BytesIO(b'too much video')
        sink = io.BytesIO()
        with patch('recorder.worker.subprocess.Popen', side_effect=[source, target]), patch('recorder.worker.FILE_BYTES', 1):
            with self.assertRaises(GuardStop):
                stage_video(VIDEO, sink)
        self.assertEqual(sink.getvalue(), b'')
        self.assertTrue(target.stdout.closed)
