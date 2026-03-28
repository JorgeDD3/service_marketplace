# Demo Script (Capstone Service Marketplace)

## One-time setup (fresh machine/server)
flask --app wsgi init-db
flask --app wsgi seed
flask --app wsgi create-demo

Demo credentials:
- admin:    admin_demo@example.com / Password123!
- provider: provider_demo@example.com / Password123!
- client:   client_demo@example.com / Password123!

Run app (dev):
flask --app wsgi run --debug

Run app (prod-like):
APP_CONFIG=production SECRET_KEY='testkey' gunicorn -w 1 -b 127.0.0.1:8000 wsgi:app

## Demo Flow (5–7 minutes)

### 1) Client: browse + schedule + book
- Login as client
- Go to /services and open a service
- Pick an available time slot and create booking (pending)
- Go to /my/bookings to show scheduled datetime + status badge
- (Optional) cancel pending booking

### 2) Provider: availability + booking decision
- Login as provider
- Go to /provider/availability
  - add a window or use preset; toggle active/inactive
- Go to /provider/bookings
  - accept/decline a pending booking; show decided_at/provider_note

### 3) Admin: moderation controls
- Login as admin
- Go to /admin dashboard (metrics/links)
- /admin/services: toggle service active/inactive (verify public visibility rules)
- /admin/users: disable/enable user (guardrails)
- /admin/bookings: force-cancel with admin note
- /admin/requests: close requests

## Reset demo accounts (optional)
flask --app wsgi delete-demo
flask --app wsgi create-demo
