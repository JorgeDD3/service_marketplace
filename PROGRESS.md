# Mid-Semester Progress Summary (Service Marketplace)

## Current Status
- Core marketplace MVP: **COMPLETE**
- Admin moderation + trust workflows: **COMPLETE**
- Scheduling MVP (availability + time-off + slot booking): **COMPLETE**
- In-app messaging tied to bookings (Beyond MVP): **COMPLETE**
- Demo checkout flow (Beyond MVP): **COMPLETE**
- Deployment readiness: **IN PROGRESS** (WSGI + prod config + gunicorn tested locally; Turing deployment next)

## Completed Features

### Authentication + Security
- Register/login/logout with password hashing (Werkzeug)
- Disabled-user login blocking (`users.is_active`, disable reason)
- Role-based access control (client/provider/admin) via decorators + route guards
- Ownership checks on booking/request/messaging routes

### Marketplace Core
- Provider: profile creation + maintenance
- Provider: service creation/listing (with moderation awareness)
- Client: browse services and view detail pages
- Client: create bookings through availability-aware scheduling UI

### Booking Lifecycle + Moderation
- Booking states tracked (pending/accepted/declined/cancelled) with guarded transitions
- Provider accept/decline with decided_at and optional provider note
- Client cancel pending bookings (guarded)
- Admin: force-cancel bookings with admin note/timestamp
- Admin: services visibility moderation (active/inactive) with notes/timestamps
- Admin: enable/disable users with guardrails

### Service Requests Workflow
- Client: create and close requests
- Provider: claim and fulfill requests
- Admin: close requests
- Anti-duplication / workflow guardrails

### Scheduling System
- Weekly availability windows + presets + toggles
- Time-off blocks remove slots from availability
- Slot generation server-side (next N days, based on current build settings)
- Provider-wide conflict blocking (prevents overlapping commitments)
- Lead-time rule (prevents last-minute bookings)
- Booking stores `booking_datetime` + `duration_minutes`
- Provider calendar/week view + booking anchors (if enabled in current build)

### Provider Verification / Trust System (Feature Milestone)
- Provider verification submission workflow with uploads
- Admin review queue + approve/reject with notes
- Admin-only secure download routes for verification docs
- Verified badge displayed throughout marketplace

### In-app Messaging (Beyond MVP)
- Conversations are 1:1 with bookings (unique `booking_id`)
- Messages: sender_id, body, timestamps
- Strict access control: only booking client/provider
- UX polish: inbox preview + timestamps, thread context + suggested prompts
- Anti-spam rate limit on sends
- **Unread tracking is DB-backed** via `conversation_reads` with `last_read_at`

### Demo Checkout (Beyond MVP)
- Booking payment tracking:
  - `payment_status` (unpaid/paid), `paid_at`, `payment_reference`
- `/checkout/<booking_id>` fake checkout UI (method selection + card fields)
- Server-side demo validation (does not store payment details)
- Workflow gating:
  - Messaging requires paid booking (unpaid redirects to checkout)
  - Provider cannot accept/decline until paid
  - Client cannot cancel after paid
- Payment badge + reference displayed on client/provider booking lists

## Deployment Readiness Work Done
- Added `wsgi.py` entrypoint
- Added ProductionConfig / DevelopmentConfig with `APP_CONFIG` switch
- Enforced `SECRET_KEY` in production
- Gunicorn tested locally in production-like mode
- CLI commands:
  - `init-db`, `seed`, `create-demo`, `delete-demo`
- Runbooks/docs created:
  - `DEPLOYMENT.md`, `TURING_CHECKLIST.md`, `ARCHITECTURE.md`, `SCHEMA.md`, `ROUTES.md`
- Git initialized and pushed to GitHub:
  - Remote: `https://github.com/JorgeDD3/service_marketplace`

## Next Goals (Immediate)
1. **Deploy to Turing**
   - Configure env vars (APP_CONFIG=production, SECRET_KEY, etc.)
   - Install deps + init DB + create demo accounts
   - Confirm live URL reachable for grading
2. **Smoke test the full demo flow on the hosted instance**
   - Book → Checkout → Pay → Message → Provider Accept
   - Admin moderation actions
3. **Final polish**
   - Small UI consistency pass
   - Documentation final pass (ensure Beyond MVP features are clearly labeled)
   - Update ERD in draw.io to include messaging + checkout additions (Beyond MVP)
