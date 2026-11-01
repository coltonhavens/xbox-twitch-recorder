import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from recorder.authorize_drive import load_web_client
from recorder import mac_authorize


def client():
    return {'web':{'project_id':'xbox-twitch-recorder','client_id':'fake-client',
        'client_secret':'fake-secret','auth_uri':'https://accounts.google.com/o/oauth2/auth',
        'token_uri':'https://oauth2.googleapis.com/token','redirect_uris':['http://localhost:8765/callback'],
        'javascript_origins':['http://localhost:8765']}}


class MacAuthorizationTests(unittest.TestCase):
    def test_existing_web_client_validation(self):
        with tempfile.TemporaryDirectory() as scratch:
            file = Path(scratch)/'existing client.json'
            file.write_text(json.dumps(client()))
            self.assertEqual(load_web_client(file)['web']['project_id'], 'xbox-twitch-recorder')
            for field, value in (('project_id','other-project'), ('redirect_uris',[]),
                                 ('javascript_origins',['https://other.invalid']), ('token_uri','https://evil.invalid/token')):
                changed = client()
                changed['web'][field] = value
                file.write_text(json.dumps(changed))
                with self.subTest(field=field), self.assertRaises(ValueError):
                    load_web_client(file)
            file.write_text(json.dumps({'installed':client()['web']}))
            with self.assertRaises(ValueError):
                load_web_client(file)

    def test_mac_launcher_uses_private_temporary_copies_and_removes_them(self):
        with tempfile.TemporaryDirectory() as scratch:
            source = Path(scratch)/'downloaded client.json'
            source.write_text(json.dumps(client()))
            temporary_files = []
            def command(args, **kwargs):
                if args[:2] == ['gh','api']:
                    return Mock(returncode=0, stdout='true\n')
                if args[0] != 'gh':
                    self.assertIn('--open-browser',args)
                    self.assertIn('--github-secret',args)
                    self.assertNotIn('fake-picker-secret',args)
                    for flag in ('--client-file','--picker-key-file'):
                        file = Path(args[args.index(flag)+1])
                        self.assertEqual(file.stat().st_mode & 0o777,0o600)
                        temporary_files.append(file)
                    self.assertEqual(temporary_files[1].read_text(),'fake-picker-secret')
                return Mock(returncode=0)
            with patch('sys.platform','darwin'), patch('recorder.mac_authorize.shutil.which',return_value='/usr/bin/gh'), patch('recorder.mac_authorize.selected_client',return_value=source), patch('builtins.input',return_value='123456'), patch('recorder.mac_authorize.getpass.getpass',return_value='fake-picker-secret'), patch('recorder.mac_authorize.subprocess.run',side_effect=command), patch('builtins.print') as output:
                mac_authorize.main()
            self.assertEqual(len(temporary_files),2)
            self.assertTrue(all(not path.exists() for path in temporary_files))
            self.assertTrue(source.exists())
            self.assertNotIn('fake-picker-secret',str(output.call_args_list))

    def test_wrong_github_account_stops_before_google_consent_or_secret_prompt(self):
        with patch('sys.platform','darwin'), patch('recorder.mac_authorize.shutil.which',return_value='/usr/bin/gh'), patch('recorder.mac_authorize.subprocess.run',side_effect=[Mock(returncode=0),Mock(returncode=0,stdout='false\n')]), patch('recorder.mac_authorize.selected_client') as select:
            with self.assertRaises(SystemExit):
                mac_authorize.main()
            select.assert_not_called()

    def test_non_mac_launcher_does_not_run_any_command(self):
        with patch('sys.platform','linux'), patch('recorder.mac_authorize.subprocess.run') as command:
            with self.assertRaises(SystemExit):
                mac_authorize.main()
            command.assert_not_called()
