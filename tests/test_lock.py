import copy
import json
import sys
import types
import unittest
from unittest.mock import patch
from recorder.worker import Bucket


class NotFound(Exception):
    pass


class PreconditionFailed(Exception):
    pass


class Blob:
    def __init__(self, shared):
        self.shared, self.generation = shared, None
    def reload(self):
        if not self.shared:
            raise NotFound()
        self.generation = self.shared['generation']
    def download_as_text(self, if_generation_match):
        if self.shared.get('generation') != if_generation_match:
            raise PreconditionFailed()
        return self.shared['text']
    def upload_from_string(self, text, if_generation_match, **kwargs):
        if self.shared.get('generation', 0) != if_generation_match:
            raise PreconditionFailed()
        self.generation = self.shared.get('generation', 0) + 1
        self.shared.update(generation=self.generation, text=text)
    def delete(self, if_generation_match):
        if self.shared.get('generation') != if_generation_match:
            raise PreconditionFailed()
        self.shared.clear()


class LockTests(unittest.TestCase):
    def worker(self, shared, owner):
        worker = Bucket.__new__(Bucket)
        worker.bucket = types.SimpleNamespace(blob=lambda key: Blob(shared))
        worker.owner = owner
        worker.lock_generation = None
        worker.deadline = 0
        return worker

    def setUp(self):
        exceptions = types.ModuleType('google.api_core.exceptions')
        exceptions.NotFound, exceptions.PreconditionFailed = NotFound, PreconditionFailed
        self.patch = patch.dict(sys.modules, {'google.api_core.exceptions': exceptions})
        self.patch.start()
    def tearDown(self):
        self.patch.stop()

    def test_overlapping_schedule_cannot_acquire_active_lease(self):
        shared = {}
        first, second = self.worker(shared, 'first'), self.worker(shared, 'second')
        self.assertTrue(first.acquire(100))
        self.assertFalse(second.acquire(101))
        self.assertEqual(json.loads(shared['text'])['owner'], 'first')
        first.release()
        self.assertTrue(second.acquire(102))

    def test_expired_holder_cannot_delete_replacement_lease(self):
        shared = {}
        first, second = self.worker(shared, 'first'), self.worker(shared, 'second')
        self.assertTrue(first.acquire(100))
        self.assertTrue(second.acquire(first.deadline + 1))
        with self.assertRaises(PreconditionFailed):
            first.release()
        self.assertEqual(json.loads(shared['text'])['owner'], 'second')

    def test_expired_worker_stops_before_side_effects(self):
        worker = self.worker({}, 'first')
        self.assertTrue(worker.acquire(100))
        with patch('recorder.worker.time.time', return_value=worker.deadline):
            with self.assertRaises(RuntimeError):
                worker.assert_lease()
