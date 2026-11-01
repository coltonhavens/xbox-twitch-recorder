import copy
import sys
import time
import unittest
from unittest.mock import patch
from recorder.guards import Budget, GuardStop, FILE_BYTES, MONTH_SECONDS, MONTH_BYTES, MAX_RUN_SECONDS, STAGING_BYTES
from recorder.supervisor import supervise


class Store:
    def __init__(self):
        self.rows = {}
        self.bytes = 0
        self.oldest = None
    def read(self, key):
        return copy.deepcopy(self.rows.get(key, {}))
    def save(self, key, value):
        self.rows[key] = copy.deepcopy(value)
    def staging_usage(self):
        return self.bytes, self.oldest


class GuardTests(unittest.TestCase):
    def test_monthly_run_reservation_survives_crash_then_normal_reconciles(self):
        store = Store()
        crashed = Budget(store, 1793570000)
        crashed.reserve_run()
        later = Budget(store, 1793570010)
        self.assertEqual(later.data['reserved_seconds'], MAX_RUN_SECONDS)
        later.reserve_run()
        later.finish_run(1793570070)
        self.assertEqual(later.data['reserved_seconds'], MAX_RUN_SECONDS + 180)

    def test_runtime_and_download_limits_fail_before_work(self):
        store = Store()
        budget = Budget(store, 1793570000)
        budget.data['reserved_seconds'] = MONTH_SECONDS
        with self.assertRaises(GuardStop):
            budget.reserve_run()
        budget.data['reserved_bytes'] = MONTH_BYTES
        with self.assertRaises(GuardStop):
            budget.reserve_download()

    def test_download_reconciliation_and_live_cap(self):
        store = Store()
        budget = Budget(store, 1793570000)
        budget.admit_stage()
        budget.downloaded(1234)
        self.assertEqual(store.rows[budget.key]['reserved_bytes'], 1234)
        store.bytes = STAGING_BYTES - FILE_BYTES + 1
        with self.assertRaises(GuardStop):
            budget.admit_stage()
        self.assertEqual(store.rows[budget.key]['reserved_bytes'], 1234)

    def test_vod_retries_back_off_and_stop_at_five(self):
        store, state = Store(), {}
        budget = Budget(store, 1793570000)
        self.assertTrue(budget.begin_attempt(state, '123', 0))
        self.assertFalse(budget.begin_attempt(state, '123', 10))
        for _ in range(4):
            self.assertTrue(budget.begin_attempt(state, '123', state['retry_after']))
        with self.assertRaises(GuardStop):
            budget.begin_attempt(state, '123', state['retry_after'])
        self.assertEqual(store.rows['123']['attempts'], 5)

    def test_month_rollover_is_separate_utc_ledger(self):
        store = Store()
        november = Budget(store, 1793570000)
        november.reserve_run()
        december = Budget(store, 1796162000)
        self.assertNotEqual(november.key, december.key)
        self.assertEqual(december.data['reserved_seconds'], 0)

    def test_backlog_alert_without_deleting_media(self):
        store = Store()
        store.oldest = time.time() - 90000
        with patch('recorder.guards.emit') as event:
            Budget(store).check_staging()
        self.assertEqual(event.call_args.args[0], 'staging_backlog')
        self.assertIsNotNone(store.oldest)

    def test_supervisor_success_failure_and_real_child_timeout(self):
        with patch('recorder.supervisor.emit') as event:
            self.assertEqual(supervise([sys.executable, '-c', 'pass'], 5), 0)
            self.assertEqual(supervise([sys.executable, '-c', 'raise SystemExit(7)'], 5), 7)
            self.assertEqual(supervise([sys.executable, '-c', 'import time; time.sleep(60)'], .05), 124)
            names = [call.args[0] for call in event.call_args_list]
            self.assertIn('runtime_limit', names)
            self.assertIn('run_failed', names)

    def test_no_worker_start_if_runtime_limit_exceeds_safety_ceiling(self):
        with patch('recorder.supervisor.subprocess.Popen') as spawn:
            with self.assertRaises(ValueError):
                supervise(['unused'], 99999)
            spawn.assert_not_called()

    def test_corrupt_budget_is_not_silently_reset(self):
        store = Store()
        budget = Budget(store, 1793570000)
        store.rows[budget.key] = {'reserved_seconds': float('nan'), 'reserved_bytes': 0}
        with self.assertRaises(GuardStop):
            Budget(store, 1793570000)

    def test_alert_failure_does_not_block_terminal_reporting(self):
        import os
        from recorder.events import emit
        with patch.dict(os.environ, {'ALERTS_ENABLED': 'false'}), patch('builtins.print') as output:
            emit('runtime_limit', 'ERROR', seconds=19800)
        self.assertIn('runtime_limit', output.call_args.args[0])

    def test_cloud_alert_transport_failure_is_contained(self):
        import os
        import types
        from unittest.mock import Mock
        from recorder.events import emit
        google = types.ModuleType('google')
        auth = types.ModuleType('google.auth')
        auth.default = Mock(side_effect=RuntimeError('test transport failure'))
        google.auth = auth
        requests = types.ModuleType('google.auth.transport.requests')
        requests.AuthorizedSession = Mock()
        with patch.dict(sys.modules, {'google': google, 'google.auth': auth, 'google.auth.transport.requests': requests}), patch.dict(os.environ, {'ALERTS_ENABLED': 'true'}), patch('builtins.print') as output:
            emit('runtime_limit', 'ERROR', seconds=19800)
        self.assertIn('alert_transport_failed', output.call_args.args[0])

    def test_exited_leader_does_not_leave_descendants_unsignalled(self):
        import signal
        from unittest.mock import Mock, call
        from recorder.supervisor import terminate_group
        child = Mock(pid=12345)
        child.poll.return_value = 0
        with patch('recorder.supervisor.os.killpg') as send:
            terminate_group(child)
        self.assertEqual(send.call_args_list, [call(12345, signal.SIGTERM), call(12345, signal.SIGKILL)])
