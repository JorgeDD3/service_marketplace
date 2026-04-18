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

---

## Demo Flow (7–10 minutes)

### 1) Client: browse + schedule + book → checkout (demo)
- Login as client
- Go to `/services` and open a service
- Pick an available time slot and create booking (pending)
- You should be redirected to **`/checkout/<booking_id>`**
- Show the checkout UI (payment method + card fields)
  - Submit demo payment (marks booking as **paid**, stores `paid_at` + `payment_reference`)
- Go to `/my/bookings`
  - Show scheduled datetime + status badge
  - Show **paid/unpaid** badge + paid timestamp/ref if paid
  - Note: paid bookings cannot be client-canceled (guarded)

### 2) Client ↔ Provider: messaging tied to the booking (Beyond MVP)
- From the paid booking, click **Messages**
- Send a message (suggested questions are a nice touch if visible)
- Go back to `/messages` inbox to show:
  - last-message preview
  - timestamp
  - **unread dot** behavior (DB-backed)

### 3) Provider: availability + booking decision (pay-gated)
- Login as provider
- Go to `/provider/availability`
  - add a window or use preset; toggle active/inactive
- Go to `/provider/bookings`
  - Show **paid/unpaid** badge on bookings
  - Note: **Accept/Decline is only available once paid** (guarded + UI-gated)
  - Accept/decline a pending paid booking; show `decided_at` and provider note

### 4) Admin: moderation + trust controls
- Login as admin
- Go to `/admin/` dashboard (metrics/links)
- `/admin/services`: toggle service active/inactive (verify public visibility rules)
- `/admin/users`: disable/enable user (guardrails)
- `/admin/bookings`: force-cancel with admin note
- `/admin/requests`: close requests
- (If enabled in your build) provider verification queue:
  - `/admin/verifications` approve/reject + download docs (admin-only)

---

## Reset demo accounts (optional)
flask --app wsgi delete-demo
flask --app wsgi create-demo