#!/usr/bin/env python3
"""Upload rendered clips to Drive: <stream archive folder>/Daily Clips/<date>/<name>.mp4
Uses the recorder's existing owner-approved drive.file credential (XTR_DRIVE_AUTH); creates no new OAuth client.
usage: upload_to_drive.py DATE FILE.mp4 [FILE.mp4 ...]   (skips a file already uploaded under the same name)"""
import json, os, sys
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

ARCHIVE_FOLDER = "1X9VfSes_byvkygreHfdvGNHzVXjvAYBG"      # existing MrHype420 Drive folder (picked by Colton)
FOLDER_MIME = "application/vnd.google-apps.folder"

config = json.loads(os.environ.pop("XTR_DRIVE_AUTH"))
oauth = config["oauth"]
if set(oauth.get("scopes", [])) != {"https://www.googleapis.com/auth/drive.file"}:
    raise SystemExit("Require exactly owner drive.file authorization")
api = build("drive", "v3", credentials=Credentials.from_authorized_user_info(oauth), cache_discovery=False)

def child(parent, name, mime=None):
    q = f"'{parent}' in parents and name = '{name}' and trashed = false" + (f" and mimeType = '{mime}'" if mime else "")
    hits = api.files().list(q=q, fields="files(id,name,size)", spaces="drive").execute(num_retries=3).get("files", [])
    return hits[0] if hits else None

def folder(parent, name):
    f = child(parent, name, FOLDER_MIME)
    if f:
        return f["id"]
    return api.files().create(body={"name": name, "mimeType": FOLDER_MIME, "parents": [parent]},
                              fields="id").execute(num_retries=3)["id"]

date, files = sys.argv[1], sys.argv[2:]
day = folder(folder(ARCHIVE_FOLDER, "Daily Clips"), date)
for path in files:
    name = os.path.basename(path)
    have = child(day, name)
    if have and int(have.get("size", 0)) == os.path.getsize(path):
        print("already in Drive:", name); continue
    media = MediaFileUpload(path, mimetype="video/mp4", resumable=True, chunksize=8 * 1024 * 1024)
    req = api.files().create(body={"name": name, "parents": [day]}, media_body=media, fields="id,size")
    resp = None
    while resp is None:
        _, resp = req.next_chunk(num_retries=5)
    if int(resp["size"]) != os.path.getsize(path):
        raise SystemExit(f"size mismatch for {name}")
    print("uploaded:", name, resp["id"])
print(f"https://drive.google.com/drive/folders/{day}")
