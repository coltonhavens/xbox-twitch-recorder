import json
from pathlib import Path
import unittest


class DeploymentTests(unittest.TestCase):
    def test_vm_safeguards_and_disabled_gates(self):
        intent = json.loads(Path('deploy/vm-intent.json').read_text())
        self.assertEqual(intent['vm']['machine_type'], 'e2-small')
        self.assertEqual(intent['vm']['scheduling']['instanceTerminationAction'], 'STOP')
        self.assertEqual(intent['vm']['scheduling']['maxRunDuration']['seconds'], 21600)
        self.assertFalse(intent['scheduler']['enabled'])
        self.assertFalse(intent['archive_enabled'])
        service = Path('deploy/systemd/xtr-archive.service').read_text()
        self.assertIn('ExecStopPost=+/usr/bin/systemctl --no-block poweroff', service)
        self.assertIn('RuntimeMaxSec=5h45m', service)
        self.assertIn('KillMode=control-group', service)
        self.assertIn('OnBootSec=5h50m', Path('deploy/systemd/xtr-poweroff.timer').read_text())
        self.assertIn('OnBootSec=5m', Path('deploy/systemd/xtr-boot-deadline.timer').read_text())
        self.assertEqual(intent['buckets']['staging_soft_delete_seconds_proposal'], 0)

    def test_alert_templates_have_no_active_notification_destination(self):
        for path in Path('deploy/alerts').glob('*.json'):
            policy = json.loads(path.read_text())
            if 'notificationChannels' in policy:
                self.assertEqual(policy['notificationChannels'], [])
                self.assertFalse(policy['enabled'])
        budget = json.loads(Path('deploy/alerts/budget.json').read_text())
        self.assertEqual(budget['amount']['specifiedAmount']['units'], '10')
