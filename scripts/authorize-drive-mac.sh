#!/bin/bash
# One-time local setup only: no merge, workflow activation or Google settings changes.
set -euo pipefail
if [ "$(uname -s)" != Darwin ]; then
  echo 'Run this launcher in Terminal on your Mac.' >&2
  exit 1
fi
repo_root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$repo_root"
command -v python3 >/dev/null || { echo 'Install Python 3 first.' >&2; exit 1; }
command -v gh >/dev/null || { echo 'Install GitHub CLI first: brew install gh' >&2; exit 1; }
umask 077
mkdir -p work
python3 -m venv work/drive-auth-venv
work/drive-auth-venv/bin/python -m pip install --disable-pip-version-check --no-cache-dir -r recorder/requirements.txt
exec work/drive-auth-venv/bin/python -m recorder.mac_authorize
