import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
from recorder.worker import Journal, Drive, FOLDER, digest, probe, publish, upload_pass, STOP


class FakeDrive:
    def __init__(self, fail=False):
        self.calls = []
        self.fail = fail

    def allocate(self):
        return 'durable-drive-id'

    def upload(self, path, file_id, sha):
        self.calls.append(file_id)
        if self.fail:
            raise TimeoutError()
        return file_id


class WorkerTests(unittest.TestCase):
    def setUp(self):
        STOP.clear()
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.journal = Journal(self.root / 'journal.sqlite3')
        self.path = self.root / 'capture-123-abc-00000000.ts'
        self.path.write_bytes(b'test recording')
        self.metadata = {'streams': [{'codec_type': 'video'}, {'codec_type': 'audio'}]}

    def tearDown(self):
        self.journal.db.close()
        self.tmp.cleanup()

    def test_failure_keeps_bytes_and_reuses_durable_id_after_restart(self):
        failed = FakeDrive(True)
        with patch('recorder.worker.probe', return_value=self.metadata):
            upload_pass(self.root, self.journal, failed)
            self.assertTrue(self.path.exists())
            self.journal.db.close()
            self.journal = Journal(self.root / 'journal.sqlite3')
            good = FakeDrive()
            upload_pass(self.root, self.journal, good)
        self.assertEqual(failed.calls, good.calls)
        self.assertFalse(self.path.exists())

    def test_completed_upload_crash_before_delete_does_not_reupload(self):
        self.journal.stage(self.path)
        self.journal.identify(self.path.name, 'existing')
        self.journal.complete(self.path.name)
        drive = FakeDrive()
        with patch('recorder.worker.probe', return_value=self.metadata):
            upload_pass(self.root, self.journal, drive)
        self.assertEqual(drive.calls, [])
        self.assertFalse(self.path.exists())

    def test_changed_chunk_rejected(self):
        self.journal.stage(self.path)
        self.path.write_bytes(b'changed')
        with self.assertRaises(RuntimeError):
            self.journal.stage(self.path)

    def test_drive_checks_destination_size_and_checksum(self):
        sha = digest(self.path)
        remote = {'id': 'x', 'size': str(self.path.stat().st_size), 'parents': [FOLDER],
                  'md5Checksum': digest(self.path, 'md5'), 'appProperties': {'xtr_sha256': sha}}
        self.assertEqual(Drive.verify(self.path, remote, sha), 'x')
        for key, value in [('size', '0'), ('parents', ['wrong']), ('md5Checksum', 'wrong')]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                Drive.verify(self.path, dict(remote, **{key: value}), sha)

    def test_publisher_keeps_open_segment_then_recovers_final(self):
        session = self.root / 'capture-456-def'
        session.mkdir()
        for name in ['00000000.ts', '00000001.ts']:
            (session / name).write_bytes(b'data')
        publish(session, self.root, False)
        self.assertEqual([p.name for p in session.iterdir()], ['00000001.ts'])
        publish(session, self.root, True)
        self.assertFalse(session.exists())

    def test_bad_media_is_retained(self):
        upload_pass(self.root, self.journal, FakeDrive())
        self.assertTrue((self.root / 'quarantine' / self.path.name).exists())

    def test_real_ffmpeg_preserves_audio_in_segmented_live_format(self):
        self.path.unlink()
        subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc=size=160x90:rate=10',
                        '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000', '-t', '4',
                        '-c:v', 'mpeg2video', '-g', '10', '-c:a', 'aac', '-f', 'mpegts',
                        str(self.root / 'fixture.ts')], check=True, timeout=30)
        subprocess.run(['ffmpeg', '-v', 'error', '-i', str(self.root / 'fixture.ts'), '-map', '0:v:0',
                        '-map', '0:a?', '-c', 'copy', '-f', 'segment', '-segment_time', '1',
                        '-reset_timestamps', '1', '-segment_format', 'mpegts', str(self.root / '%03d.ts')],
                       check=True, timeout=30)
        parts = sorted(self.root.glob('[0-9]*.ts'))
        self.assertGreaterEqual(len(parts), 3)
        for part in parts:
            data = probe(part)
            self.assertEqual({s['codec_type'] for s in data['streams']}, {'video', 'audio'})


if __name__ == '__main__':
    unittest.main()
