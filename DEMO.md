# Demo Script (ServiceSphere Capstone)

This is a quick, repeatable demo flow you can run in ~7–10 minutes.
It’s written to match the current build: booking + demo checkout + booking-tied messaging + admin moderation.

## One-time setup (local dev only)
If you’re on a fresh machine/database:

```bash
flask --app wsgi init-db
flask --app wsgi seed
flask --app wsgi create-demo

Demo credentials:

admin: admin_demo@example.com / Password123!
provider: provider_demo@example.com / Password123!
client: client_demo@example.com / Password123!

Run app (dev):

flask --app wsgi run --debug

Run app (prod-like locally):

APP_CONFIG=production SECRET_KEY='testkey' gunicorn wsgi:app --bind 127.0.0.1:8000 --workers 1

If you’re demoing the deployed build (Railway), you don’t run commands — just use the live URL.

Demo Flow (7–10 minutes)
  1) Client: browse → schedule → book → checkout (demo)
Login as client
Go to /services and open a service
Pick an available time slot and submit booking (status  starts as pending)
You should be redirected to /checkout/<booking_id>
Show the checkout UI (payment method + demo card fields)
Submit demo payment (marks booking as paid, stores paid_at + payment_reference)
Go to /my/bookings
Show scheduled datetime + status badge
Show paid/unpaid state and the paid timestamp/reference
Note: paid bookings can’t be client-cancelled (guarded)
2) Client ↔ Provider: messaging is tied to the booking
From the paid booking, click Messages
Send a message
Go back to /messages inbox to show:
last-message preview
timestamp
unread indicator behavior (DB-backed)
3) Provider: availability + booking decision (pay-gated)
Login as provider
Go to /provider/availability
add a window or use a preset; toggle active/inactive
Go to /provider/bookings
Show paid/unpaid badges
Note: Accept/Decline is only available once paid (guarded + UI-gated)
Accept/decline a pending paid booking; show decided_at and optional provider note
4) Provider: time off + calendar view (scheduling MVP)
Go to /provider/time-off
add a time off block
Go to /provider/calendar
show the time off block appears (purple overlay)
show how bookings appear on the week timeline
5) Admin: moderation + trust controls
Login as admin
Go to /admin/ (moderation hub)
/admin/services: hide/unhide a service (verify public visibility rules)
/admin/users: disable/enable user (guardrails apply)
/admin/bookings: force-cancel with an admin note
/admin/requests: close client service requests
Provider verification queue (if used in your build):
/admin/verifications: approve/reject + download docs (admin-only)
Reset demo accounts (optional, local dev)
flask --app wsgi delete-demo
flask --app wsgi create-demo