"""Boot-only secret loading to tmpfs. Run as root from an immutable installation."""
import base64
import os
from pathlib import Path
import pwd

PROJECT = 'xbox-twitch-recorder'


def load():
    if os.environ.get('ARCHIVE_ENABLED') != 'true':
        return  # Disabled installation performs no API request.
    import google.auth
    from google.auth.transport.requests import AuthorizedSession
    credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
    user = pwd.getpwnam('xtr')
    root = Path('/run/xtr')
    root.mkdir(mode=0o700, exist_ok=True)
    os.chown(root, user.pw_uid, user.pw_gid)
    with AuthorizedSession(credentials) as session:
        for name, filename in (('twitch-client-secret', 'twitch-client-secret'), ('drive-owner-oauth', 'authorized-user.json')):
            response = session.get('https://secretmanager.googleapis.com/v1/projects/' + PROJECT + '/secrets/' + name + '/versions/latest:access', timeout=20)
            response.raise_for_status()
            data = base64.b64decode(response.json()['payload']['data'], validate=True)
            path = root / filename
            # /run/xtr must be root-created at boot, without inherited files/symlinks.
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, 'wb') as secret:
                os.fchown(secret.fileno(), user.pw_uid, user.pw_gid)
                secret.write(data)


if __name__ == '__main__':
    try:
        load()
    except Exception as exc:
        from .events import emit
        emit('secret_load_failed', 'ERROR', error_type=type(exc).__name__)
        raise SystemExit('Secret loading failed; review redacted event')
