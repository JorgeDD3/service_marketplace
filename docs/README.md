# ServiceSphere (Capstone Service Marketplace)

ServiceSphere is a web-based service marketplace built for my CS capstone. It supports three roles:

- **Clients** browse services, request bookings, and message providers
- **Providers** manage services, availability, time off, and booking decisions
- **Admins** moderate users/services, handle refunds, and review provider verification

## Live Deployment (Railway)
- **URL:** https://servicemarketplace-production.up.railway.app

Railway auto-deploys from GitHub pushes to the connected branch.

## Tech Stack
- Python 3.11
- Flask (App Factory Pattern)
- Flask-SQLAlchemy
- Flask-Login
- SQLite (local dev)
- PostgreSQL (production on Railway)

## Demo Accounts (local dev seed)
After running the demo seed commands below:

- admin:    `admin_demo@example.com` / `Password123!`
- provider: `provider_demo@example.com` / `Password123!`
- client:   `client_demo@example.com` / `Password123!`

## Local Setup
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

```

## Initialize database + seed demo data (local)

`flask --app wsgi init-db`
`flask --app wsgi seed`
`flask --app wsgi create-demo`

## Run locally
`flask --app wsgi run --debug`

## Optional “prod-like” local run:

`APP_CONFIG=production SECRET_KEY='testkey' gunicorn wsgi:app --bind 127.0.0.1:8000 --workers 1`

## Quick Feature Tour (grader path)
1) Client: /services → open a service → book → /checkout/<id> → pay (demo) → /my/bookings

2) Messages: open booking → Messages → /messages

3) Provider: /provider/dashboard → Availability / Calendar / Bookings
4) Admin: /admin/ → moderation hub + services/users/bookings/requests/verifications

## Documentation Index

## Diagrams
    ERD: docs/ERD - Mar 13.png
    ERD: docs/ERD - Apr 11.png

## Reference Docs
    Architecture: ARCHITECTURE.md
    Route map (grouped): ROUTE_MAP.md
    Raw routes dump: ROUTES.md
    Database schema dump: SCHEMA.md
    Demo script: DEMO.md
    Deployment runbook: DEPLOYMENT.md

## Useful CLI Commands
Initialize DB: `flask --app wsgi init-db`
Seed roles: `flask --app wsgi seed`
Create demo accounts: `flask --app wsgi create-demo`
Delete demo accounts: `flask --app wsgi delete-demo`

### Verification
```bash
python -m py_compile wsgi.py
```