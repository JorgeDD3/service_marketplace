# Deployment (Turing)

This project is a Flask service marketplace using an app factory pattern.
Production is served via `wsgi.py`.

## Requirements
- Python 3.11
- Virtualenv
- Dependencies installed from `requirements.txt`

## Environment variables

### Local development
Copy `.env.example` to `.env` and adjust as needed:

- `APP_CONFIG=development`
- `SECRET_KEY=dev-only-change-me`

### Production (Turing)
Set these in your shell/session (do not commit real secrets):

- `APP_CONFIG=production`
- `SECRET_KEY=<strong random string>`
- Optional: `DATABASE_URL=<db uri>`

Example:

export APP_CONFIG=production
export SECRET_KEY='replace-with-a-long-random-string'

## One-time database setup (recommended in production)
Create tables:

flask --app wsgi init-db

Seed roles (idempotent):

flask --app wsgi seed

## Production sanity check
APP_CONFIG=production SECRET_KEY='replace-me' python -c "from wsgi import app; print(app.config['DEBUG'])"
Expected output: False

## Gunicorn (typical on Linux servers)
From the project root:

gunicorn -w 2 -b 0.0.0.0:8000 wsgi:app

Then visit:
http://<server-hostname>:8000

## Notes
- In production, the app refuses to start if `SECRET_KEY` is missing/weak.
- SQLite default path is `instance/site.db` unless `DATABASE_URL` is provided.
