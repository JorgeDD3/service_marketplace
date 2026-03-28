# Mid-Semester Progress Summary (Service Marketplace)

## Current Status
- Core marketplace MVP: COMPLETE
- Admin moderation: COMPLETE
- Scheduling MVP (local availability + slot booking): COMPLETE
- Deployment readiness: IN PROGRESS (WSGI + prod config + gunicorn tested locally)

## Completed Features
- Auth: register/login/logout, password hashing, disabled-user login blocking
- RBAC: client/provider/admin protected routes + ownership checks
- Provider: profile creation, service creation/listing, provider dashboards
- Client: browse services, create bookings, cancel pending bookings
- Booking lifecycle: provider accept/decline (guarded), admin force-cancel
- Service requests: client create/close, provider claim/fulfill, admin close
- Moderation:
  - Services: active/inactive visibility enforcement + notes/timestamps
  - Users: enable/disable with guardrails
  - Bookings: admin actions with notes/timestamps
- Scheduling:
  - Weekly availability windows + presets + toggles
  - Slot generation (next 7 days)
  - Provider-wide conflict blocking
  - Pending hold expiry (30 min)
  - Booking stores booking_datetime + duration_minutes

## Deployment Readiness Work Done
- Added `wsgi.py` entrypoint
- Added ProductionConfig / DevelopmentConfig with APP_CONFIG switch
- Enforced SECRET_KEY in production
- Added Gunicorn dependency and verified production-mode boot locally
- Added `init-db`, `seed`, `create-demo`, `delete-demo` CLI commands
- Added deployment + demo runbooks and documentation index

## Next Goals (Before/After Monday)
- Deploy to Turing (gunicorn/uWSGI depending on environment)
- Confirm live URL reachable for grading
- Final polish: UI/UX tweaks, tighten scheduling overlap rules (optional)
