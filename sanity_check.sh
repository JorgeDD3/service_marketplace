#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:5000}"

echo "Sanity check against: $BASE_URL"
echo

server_header="$(curl -sI "$BASE_URL/" | tr -d '\r' | awk -F': ' 'tolower($1)=="server"{print $2}')"
if [[ -z "${server_header}" ]]; then
  echo "❌ Could not read Server header from $BASE_URL/. Is the app running?"
  exit 1
fi

# We expect Werkzeug in dev; on Turing it may be gunicorn.
if [[ "${server_header}" != *"Werkzeug"* && "${server_header}" != *"gunicorn"* ]]; then
  echo "❌ Unexpected server responding: ${server_header}"
  echo "   Make sure Flask/Gunicorn is running on this port."
  exit 1
fi

echo "✅ Server header looks good: ${server_header}"
echo

check () {
  local path="$1"
  local expected="$2"
  local code
  code="$(curl -s -o /dev/null -w "%{http_code}" "$BASE_URL$path")"
  if [[ "$code" != "$expected" ]]; then
    echo "❌ $path -> $code (expected $expected)"
    exit 1
  fi
  echo "✅ $path -> $code"
}

# Public pages
check "/" "200"
check "/services" "200"
check "/auth/login" "200"

# Protected route should redirect when logged out
check "/provider/services" "302"

# Favicon should exist
check "/favicon.ico" "200"

echo
echo "✅ All sanity checks passed."
