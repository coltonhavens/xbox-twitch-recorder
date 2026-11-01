"""Small, redacted structured events; no notification is sent until explicitly enabled."""
import json
import os


def emit(event, severity='INFO', **fields):
    payload = dict(event=event, **fields)
    print(json.dumps(dict(payload, severity=severity)), flush=True)
    if os.environ.get('ALERTS_ENABLED') != 'true':
        return
    try:
        import google.auth
        from google.auth.transport.requests import AuthorizedSession
        credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/logging.write'])
        with AuthorizedSession(credentials) as session:
            response = session.post('https://logging.googleapis.com/v2/entries:write', json={
                'logName': 'projects/xbox-twitch-recorder/logs/vod-archive',
                'resource': {'type': 'global', 'labels': {'project_id': 'xbox-twitch-recorder'}},
                'entries': [{'severity': severity, 'jsonPayload': payload}]}, timeout=10)
            response.raise_for_status()
    except Exception as exc:
        # Alert transport failure never prevents shutdown. Never print response/token.
        print(json.dumps({'severity': 'ERROR', 'event': 'alert_transport_failed', 'error_type': type(exc).__name__}), flush=True)
