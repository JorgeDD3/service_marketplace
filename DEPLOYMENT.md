# Deployment (Turing)

ServiceSphere is a Flask service marketplace (App Factory Pattern).
Production is served via `wsgi.py` (`wsgi:app`).

## Requirements
- Python 3.11
- Virtualenv
- Dependencies installed from `requirements.txt`

## Environment variables

### Local development
- `APP_CONFIG=development`
- `SECRET_KEY=dev-only-change-me`

### Production (Turing)
Set these in your shell/session (do not commit real secrets):
- `APP_CONFIG=production`
- `SECRET_KEY=<strong random string>`
- Optional: `DATABASE_URL=<db uri>` (if using Postgres/MySQL; otherwise SQLite is used)

Example:
```bash
export APP_CONFIG=production
export SECRET_KEY='replace-with-a-long-random-string'