#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
source venv/bin/activate

export APP_CONFIG=production
export URL_PREFIX="/~gddelp/service_marketplace"
export SECRET_KEY="REPLACE_WITH_A_LONG_RANDOM_STRING"

exec python -m gunicorn -w 2 -b 127.0.0.1:8001 "app:create_app()"