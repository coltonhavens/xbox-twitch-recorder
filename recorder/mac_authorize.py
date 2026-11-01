"""Mac-only one-time launcher. Select existing files; never alters OAuth settings."""
import getpass
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from .authorize_drive import load_web_client


def selected_client():
    result = subprocess.run(['osascript', '-e',
        'POSIX path of (choose file with prompt "Select your existing Xbox Twitch Recorder OAuth Web client JSON")'],
        capture_output=True, text=True, timeout=300)
    if result.returncode:
        raise ValueError('Client selection canceled')
    path = Path(result.stdout.rstrip('\n'))
    load_web_client(path)
    return path


def private_copy(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as target:
        target.write(data)


def main():
    if sys.platform != 'darwin':
        raise SystemExit('This launcher is for macOS; use recorder.authorize_drive on other systems')
    if not shutil.which('gh'):
        raise SystemExit('Install GitHub CLI first: brew install gh')
    status = subprocess.run(['gh', 'auth', 'status'], capture_output=True, timeout=30)
    if status.returncode:
        subprocess.run(['gh', 'auth', 'login', '--web', '--git-protocol', 'https'], check=True)
    # Check owner access before requesting any Google consent or creating Drive files.
    access = subprocess.run(['gh', 'api', 'repos/coltonhavens/xbox-twitch-recorder', '--jq', '.permissions.admin'],
                            capture_output=True, text=True, timeout=30)
    if access.returncode or access.stdout.strip() != 'true':
        raise SystemExit('Sign into GitHub CLI as the owner of coltonhavens/xbox-twitch-recorder')
    client = selected_client()
    number = input('Existing Google project NUMBER (numeric, not project ID): ').strip()
    if not number.isdigit():
        raise ValueError('Project number must be numeric; no authorization started')
    key = getpass.getpass('Existing Google Picker API key (hidden): ').strip()
    if not key:
        raise ValueError('Picker API key is required')
    os.umask(0o077)
    with tempfile.TemporaryDirectory(prefix='xtr-drive-authorization-') as scratch:
        client_copy, key_file = Path(scratch)/'client.json', Path(scratch)/'picker-key.txt'
        private_copy(client_copy, client.read_bytes())
        private_copy(key_file, key.encode())
        key = None
        subprocess.run([sys.executable, '-m', 'recorder.authorize_drive', '--client-file', str(client_copy),
            '--picker-key-file', str(key_file), '--project-number', number, '--github-secret', '--open-browser'], check=True)
    print('Drive authorization saved as XTR_DRIVE_AUTH. Temporary setup copies removed. Recording remains disabled.')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('Setup did not finish ('+type(exc).__name__+'). No credentials printed; no activation performed.')
        raise SystemExit(1)
