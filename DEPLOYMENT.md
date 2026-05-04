# Deployment (Railway)

ServiceSphere is a Flask service marketplace (App Factory Pattern).
Production is served via `wsgi.py` (`wsgi:app`) behind Gunicorn.

This document is the source of truth for how the deployed build runs on Railway.

## Requirements
- Python 3.11
- Dependencies installed from `requirements.txt`

## Railway deployment overview
This repo deploys using Railway’s GitHub integration.

- Pushing to the connected branch (usually `main`) triggers an automatic deploy.
- Railway builds the project and runs a single web service process.
- Environment variables and the start command are configured in the Railway dashboard.

## Environment variables

### Local development
- `APP_CONFIG=development`
- `SECRET_KEY=dev-only-change-me`

### Production (Railway)
Set these in Railway’s **Variables** tab (do not commit real secrets):
- `APP_CONFIG=production`
- `SECRET_KEY=<strong random string>`

Optional (only if you’re using a managed database):
- `DATABASE_URL=<db uri>` (Postgres is typical on Railway)

Notes:
- If `DATABASE_URL` is not set, the app will fall back to SQLite (not recommended for production).
- Keep `SECRET_KEY` stable across deploys so sessions don’t invalidate unexpectedly.

## Start command
Railway must run a web server that binds to the port it provides via `$PORT`.

Recommended start command:
```bash
gunicorn wsgi:app --bind 0.0.0.0:$PORT
```