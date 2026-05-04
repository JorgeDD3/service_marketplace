# Deployment (Railway)

ServiceSphere is a Flask service marketplace (App Factory Pattern).
Production is served via `wsgi.py` (`wsgi:app`).

This document is the source of truth for how the deployed build runs on Railway.

## Requirements
- Python 3.11
- Dependencies installed from `requirements.txt`

## Railway deployment overview
Railway builds the project from your GitHub repo and runs a single web process.
You configure:
- Environment variables (secrets + config)
- The start command (how the app boots)

## Environment variables

### Local development
- `APP_CONFIG=development`
- `SECRET_KEY=dev-only-change-me`

### Production (Railway)
Set these in Railway’s Variables tab (do not commit real secrets):
- `APP_CONFIG=production`
- `SECRET_KEY=<strong random string>`

Optional (only if you’re using a managed database):
- `DATABASE_URL=<db uri>` (Postgres is typical on Railway)

Notes:
- If `DATABASE_URL` is not set, the app will fall back to SQLite (not recommended for production).
- Keep `SECRET_KEY` stable across deploys so sessions don’t invalidate unexpectedly.

## Start command
Railway needs a command that runs the web server and exposes the port provided by Railway.

Recommended start command:
```bash
gunicorn wsgi:app --bind 0.0.0.0:$PORT