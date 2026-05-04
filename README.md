# ServiceSphere (Service Marketplace Capstone)

ServiceSphere is a Flask-based service marketplace built for my CS capstone. It supports three roles:

- **Clients** browse services, request bookings, complete a demo checkout, and message providers
- **Providers** manage services, availability, time off, and booking decisions
- **Admins** moderate users/services, review provider verification, and handle refund requests

## Live Deployment (Railway)
- **URL:** https://servicemarketplace-production.up.railway.app

Railway deploys automatically from GitHub pushes to the connected branch.

## Stack
- Python 3.11
- Flask (App Factory Pattern + Blueprints)
- Flask-SQLAlchemy
- Flask-Login
- SQLite (local dev)
- PostgreSQL (production on Railway)
- Gunicorn (production server)

## Quick Start (Local)

### 1) Create venv + install deps
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2) Initialize DB + seed demo data
```bash
flask --app wsgi init-db
flask --app wsgi seed
flask --app wsgi create-demo
```

### 3) Run the app
`flask --app wsgi run --debug`

## Open:

`http://127.0.0.1:5000`

## Demo Accounts (local dev seed)
 Created by `flask --app wsgi create-demo`:

admin: admin_demo@example.com / Password123!
provider: provider_demo@example.com / Password123!
client: client_demo@example.com / Password123!

## Quick Feature Tour (grader path)
1) Client: /services → open a service → book → /checkout/<id> → pay (demo) → /my/bookings

2) Messages: open booking thread → /messages

3) Provider: /provider/dashboard → Availability / Calendar / Bookings

4) Admin: /admin/ → moderation hub + services/users/bookings/requests/verifications

## Useful Commands

Reset demo environment (local):
```bash
flask --app wsgi delete-demo
flask --app wsgi init-db
flask --app wsgi seed
flask --app wsgi create-demo
```

Show routes
`flask --app wsgi routes`

## Docs
Docs index: docs/README.md
Architecture: ARCHITECTURE.md
Database schema dump: SCHEMA.md
Raw routes dump: ROUTES.md
Demo script: DEMO.md
Deployment runbook (Railway): DEPLOYMENT.md

## Verify
`python -m py_compile wsgi.py`
`python -m py_compile app/routes.py app/messages.py app/models.py`


### Micro-step: apply + verify formatting
After you paste that into `README.md`, run:

```bash
python - <<'PY'
from pathlib import Path
p = Path("README.md").read_text()
print("Backticks:", p.count("```"))
PY
```