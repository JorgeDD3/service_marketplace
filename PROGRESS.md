# Progress Summary (ServiceSphere)

This document is a snapshot of what’s implemented and ready to demo for final submission.

## Current Status
- Core marketplace MVP: **COMPLETE**
- Admin moderation + trust workflows: **COMPLETE**
- Scheduling MVP (availability + time-off + slot booking): **COMPLETE**
- In-app messaging tied to bookings (Beyond MVP): **COMPLETE**
- Demo checkout flow (Beyond MVP): **COMPLETE**
- Deployment readiness: **COMPLETE** (Railway + GitHub auto-deploy)

## Completed Features

### Authentication + Security
- Register/login/logout with password hashing (Werkzeug)
- Password reset flow (dev shows reset link; production would email)
- Disabled-user login blocking (`users.is_active`, disable reason)
- Role-based access control (client/provider/admin) via decorators + route guards
- Ownership checks on booking/messaging/admin actions

### Marketplace Core
- Provider: profile creation + maintenance
- Provider: service creation/listing (with moderation awareness)
- Client: browse services and view detail pages
- Client: create bookings through availability-aware scheduling UI
- Client: pre-book inquiry messaging (no new tables; rate limited)

### Booking Lifecycle + Moderation
- Booking states tracked (pending/accepted/declined/cancelled) with guarded transitions
- Provider accept/decline with `decided_at` and optional provider note (pay-gated)
- Client cancel pending bookings (guarded)
- Refund request workflow stored via tags in `bookings.admin_note` (no ERD changes)
- Admin: force-cancel bookings with admin note/timestamp
- Admin: service visibility moderation (active/inactive) with notes/timestamps
- Admin: enable/disable users with guardrails (cannot disable self/last admin)

### Service Requests Workflow
- Client: submit service requests
- Provider: view requests (read-only)
- Admin: close requests

### Scheduling System
- Weekly availability windows + presets + toggles
- Supports multiple windows per day (ex: 8–10 and 12–5)
- Time-off blocks remove slots from availability
- Slot generation server-side (next N days, based on current build settings)
- Provider-wide conflict blocking (prevents overlapping commitments)
- Lead-time rule (prevents last-minute bookings)
- Booking stores `booking_datetime` + `duration_minutes`
- Provider calendar/week view with bookings + time off overlays

### Provider Verification / Trust System
- Provider verification submission workflow with uploads
- Admin review queue + approve/reject with notes
- Admin-only secure download routes for verification docs
- Verified badge displayed throughout marketplace

### In-app Messaging (Beyond MVP)
- Conversations are 1:1 with bookings (unique `booking_id`)
- Messages: `sender_id`, `body`, timestamps
- Strict access control: only booking client/provider
- Inbox preview + timestamps + thread context
- Anti-spam rate limit on sends
- **Unread tracking is DB-backed** via `conversation_reads` with `last_read_at`

### Demo Checkout (Beyond MVP)
- Booking payment tracking:
  - `payment_status` (unpaid/paid/refunded as used), `paid_at`, `payment_reference`
- `/checkout/<booking_id>` fake checkout UI (method selection + demo card fields)
- Server-side demo validation (does not store payment details)
- Workflow gating:
  - Messaging requires paid booking (unpaid redirects to checkout; inquiry threads are not pay-gated)
  - Provider cannot accept/decline until paid
  - Client cancellation/refund rules enforced server-side
- Payment badge + reference displayed on client/provider booking lists

## Deployment Notes (Final)
- Hosted on **Railway** with GitHub auto-deploy
- Production entrypoint: `wsgi.py`
- Runtime: Gunicorn (`gunicorn wsgi:app --bind 0.0.0.0:$PORT`)
- Environment variables live in Railway:
  - `APP_CONFIG=production`
  - `SECRET_KEY=...`
  - `DATABASE_URL=...` (Postgres)

## Final Polish Completed
- Repository-wide documentation/cleanup pass (file-by-file)
- Templates reorganized into role-based folders (admin/provider/services/auth)
- Removed obsolete Turing references and checklist
- Updated docs:
  - `DEPLOYMENT.md` (Railway)
  - `DEMO.md`
  - `ARCHITECTURE.md`
  - ERD placed under `docs/`

## Next Goals (If time remains)
- Keep tightening UI consistency (spacing/text)
- Final pass on route map docs to ensure they match `flask --app wsgi routes`
- One last smoke test on Railway:
  - Book → Checkout → Pay → Message → Provider Accept
  - Admin moderation actions