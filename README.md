# ServiceSphere (Service Marketplace Capstone)

A Flask-based service marketplace platform (App Factory + Blueprints) with RBAC, scheduling, moderation workflows, booking-tied messaging, and a demo checkout flow.

## Stack
- Python 3.11
- Flask (App Factory Pattern)
- Flask-SQLAlchemy
- Flask-Login
- SQLite (development)
- Gunicorn (production)

## Quick Start (Local)
### 1) Create venv + install deps
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
2) Initialize database + seed demo data
flask --app wsgi init-db
flask --app wsgi seed
flask --app wsgi create-demo
3) Run the app
flask --app wsgi run

Open: http://127.0.0.1:5000

Demo Accounts

Created by flask --app wsgi create-demo:

Admin: admin_demo@example.com / Password123!
Provider: provider_demo@example.com / Password123!
Client: client_demo@example.com / Password123!
Key Features
MVP (Design Spec)
Secure auth + RBAC (client/provider/admin)
Provider profiles + service listings
Booking workflow with guarded state transitions
Availability-aware scheduling + lead-time rule + time-off exceptions
Service requests feature
Admin moderation dashboard + guardrails
Beyond MVP (Implemented)
In-app messaging tied to bookings
/messages inbox and /messages/<conversation_id> threads
DB-backed unread tracking via conversation_reads
Demo checkout
/checkout/<booking_id> fake payment UI + server-side demo validation
Tracks payment_status, paid_at, payment_reference
Pay-gated messaging + provider accept/decline; paid bookings can’t be client-canceled
Useful Commands

Reset demo environment:

flask --app wsgi delete-demo
flask --app wsgi init-db
flask --app wsgi seed
flask --app wsgi create-demo

Show routes:

flask --app wsgi routes
Docs

See:

ARCHITECTURE.md
SCHEMA.md
ROUTES.md
DEPLOYMENT.md
TURING_CHECKLIST.md

### Verify
```bash
python -m py_compile app/routes.py app/messages.py app/models.py
Commit + push
git add README.md
git commit -m "Add README quick start and demo info"
git push