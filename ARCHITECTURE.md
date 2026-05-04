# System Architecture (ServiceSphere)

## Stack
- Python 3.11
- Flask (App Factory Pattern)
- Flask-SQLAlchemy
- Flask-Login
- SQLite (local dev)
- PostgreSQL (production on Railway)

## ERD
See: `docs/ERD - Apr 11.png`

## App Structure
- App factory: `app.create_app()` (config selected via `APP_CONFIG`)
- Blueprints:
  - `main` (public browsing + booking + demo checkout + client actions)
  - `auth` (register/login/logout + password reset flow)
  - `provider` (dashboard, profile, availability, calendar, time off)
  - `provider_services` (provider service create + “my services” list)
  - `service_requests` (client submit + admin close; legacy routes kept for compatibility)
  - `admin` (moderation hub + admin tools)
  - `messages` (booking-tied inbox + threads)

## Authentication
- Password hashing via Werkzeug
- Flask-Login session authentication
- Disabled users blocked at login (`users.is_active`, `disabled_reason`)

## Role-Based Access Control (RBAC)
- Roles: `client`, `provider`, `admin`
- Route protection uses:
  - `@login_required` for authentication
  - `@role_required(...)` for authorization
  - Ownership checks to prevent cross-account access (bookings, services, verifications)

## Moderation Workflows
- Services:
  - `services.is_active` controls public visibility
  - Admin can hide/unhide services and leave moderation notes
  - Provider can hide their own services
  - Provider **cannot** unhide services hidden by admin (moderation lock)
- Bookings:
  - State transitions guarded (pending → accepted/declined; cancel rules enforced)
  - Admin can force-cancel pending/accepted with admin note/timestamp
- Users:
  - Admin can disable/enable users
  - Guardrails: cannot disable self or last active admin
- Service Requests:
  - Clients can submit requests
  - Providers can view requests (read-only)
  - Admin can close requests

## Scheduling MVP
- Providers define weekly availability windows (`provider_availability`)
  - Multiple windows per day are supported (ex: 8–10 and 12–5)
- Providers can add one-time exceptions via `provider_time_off`
- Slot generation runs on the service detail page using:
  - weekly availability rules
  - time off ranges
  - existing bookings (pending + accepted) as busy blocks
  - lead time: clients cannot book within the next 24 hours
- Bookings store `booking_datetime` and `duration_minutes`
- Provider-wide conflict blocking across all services

## Key Tables (high level)
- `users`, `roles`
- `provider_profiles`
- `provider_availability`
- `provider_time_off`
- `provider_verifications`
- `services`
- `bookings`
- `service_requests`
- `conversations`, `messages`, `conversation_reads`
- `password_reset_tokens`

## Notable Features Implemented

### In-app Messaging (Booking-tied)
- Conversations are 1:1 with bookings:
  - `conversations.booking_id` is unique (one conversation per booking)
  - `conversations.client_id` and `conversations.provider_id` stored for permission checks
- Messages:
  - `messages` belong to a conversation and include `sender_id`, `body`, timestamps
- Access control:
  - Only the booking client/provider (or admin where allowed) can view the thread
- Unread tracking (DB-backed):
  - `conversation_reads` stores `(conversation_id, user_id, last_read_at)` with a unique constraint
  - Inbox unread state is computed from DB, not session state

### Demo Checkout (Dummy Payment)
- Booking payment fields:
  - `bookings.payment_status` (`unpaid` / `paid` / `refunded` as used)
  - `bookings.paid_at`
  - `bookings.payment_reference` (demo identifier)
- Route:
  - `GET/POST /checkout/<booking_id>` shows a fake checkout form and marks a booking as paid (demo)
- Workflow gating (demo realism):
  - Messaging is pay-gated for unpaid real bookings (inquiry threads are not gated)
  - Provider accept/decline is pay-gated: provider cannot accept/decline until booking is paid
  - Client cancel/refund request logic is enforced server-side

### Inquiry Threads (Pre-book messaging without new tables)
- Clients can send a pre-book inquiry from a service detail page
- Implementation reuses Booking + Conversation + Message:
  - creates a special inquiry “booking” tagged with `[INQUIRY]`
  - rate limited: 1 inquiry per (client, service) per 24 hours
  - inquiry bookings do not block availability slots

## Deployment Notes (Railway)
- WSGI entrypoint: `wsgi.py`
- Production server: Gunicorn (`gunicorn wsgi:app --bind 0.0.0.0:$PORT`)
- Deployments happen automatically via Railway GitHub integration
- Secrets and config live in Railway environment variables:
  - `APP_CONFIG=production`
  - `SECRET_KEY=...`
  - `DATABASE_URL=...` (Postgres)