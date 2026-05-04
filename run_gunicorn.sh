#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
source venv/bin/activate

# Local "prod-like" run helper.
# Railway uses Procfile + $PORT; this script is only for local testing.
export APP_CONFIG="${APP_CONFIG:-production}"
export SECRET_KEY="${SECRET_KEY:-dev-only-change-me}"
export PORT="${PORT:-8000}"

exec gunicorn wsgi:app --bind "127.0.0.1:${PORT}" --workers 2