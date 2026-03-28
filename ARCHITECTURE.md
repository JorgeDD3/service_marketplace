# System Architecture (Service Marketplace)

## Stack
- Python 3.11
- Flask (App Factory Pattern)
- Flask-SQLAlchemy
- Flask-Login
- SQLite (dev; configurable via DATABASE_URL)

## ERD
See: `docs/ERD - Mar 13.png`

## App Structure
- App factory: `app.create_app()` (config selected via `APP_CONFIG`)
- Blueprints:
  - `main` (public browsing + client bookings)
  - `auth` (register/login/logout)
  - `provider` (profile + availability + provider dashboard)
  - `provider_services` (provider service CRUD + moderation visibility)
  - `service_requests` (client/provider/admin workflow)
  - `admin` (moderation dashboard + actions)

## Authentication
- Password hashing via Werkzeug
- Flask-Login session authentication
- Disabled users blocked at login (`users.is_active`, `disabled_reason`)

## Role-Based Access Control (RBAC)
- Roles: `client`, `provider`, `admin`
- Route protection uses:
  - `@login_required` for authentication
  - `@role_required(...)` for authorization
  - Ownership checks to prevent cross-account access

## Moderation Workflows
- Services:
  - `services.is_active` controls public visibility
  - Admin can toggle active/inactive + leave moderation notes
  - Providers can still see their own inactive services
- Bookings:
  - Status transitions guarded (pending → accepted/declined; client cancel pending)
  - Admin can force-cancel pending/accepted with admin note/timestamp
- Users:
  - Admin can disable/enable users
  - Guardrails: cannot disable self or last active admin
- Service Requests:
  - Admin can close requests; providers can claim/fulfill; clients can close

## Scheduling MVP
- Providers define weekly availability windows (`provider_availability`)
- Client selects a generated slot (next 7 days) on service detail page
- Bookings store `booking_datetime` and `duration_minutes`
- Provider-wide conflict blocking across all services
- Pending booking hold expires after 30 minutes (prevents permanent slot locking)

## Key Tables (high level)
- `users`, `roles`
- `provider_profiles`
- `services`
- `bookings`
- `service_requests`
- `provider_availability`

## Beyond MVP Features Implemented

### In-app Messaging (Booking-tied)
- Conversations are 1:1 with bookings:
  - `conversations.booking_id` is unique (exactly one conversation per booking)
  - `conversations.client_id` and `conversations.provider_id` are stored for fast permission checks
- Messages:
  - `messages` rows belong to a conversation and include `sender_id`, `body`, timestamps
- Access control:
  - Only the booking client/provider can view and send messages
- Unread tracking (DB-backed):
  - `conversation_reads` stores `(conversation_id, user_id, last_read_at)` with a unique constraint
  - Inbox unread dot is computed from DB (last message timestamp vs `last_read_at`), not session state

### Demo Checkout (Dummy Payment)
- Booking payment tracking fields:
  - `bookings.payment_status` (`unpaid`/`paid`)
  - `bookings.paid_at`
  - `bookings.payment_reference` (demo identifier)
- Route:
  - `GET/POST /checkout/<booking_id>` shows a fake checkout form and marks a booking as paid (demo)
- Workflow gating (demo realism):
  - Messaging is pay-gated: unpaid bookings redirect to checkout before messaging routes allow access
  - Provider accept/decline is pay-gated: provider cannot accept/decline until booking is paid
  - Client cancel is pay-gated: paid bookings can’t be canceled by the client

## Deployment Notes
- WSGI entrypoint: `wsgi.py`
- Production served via Gunicorn: `gunicorn wsgi:app`
- One-time setup:
  - `flask --app wsgi init-db`
  - `flask --app wsgi seed`
  - `flask --app wsgi create-demo`
