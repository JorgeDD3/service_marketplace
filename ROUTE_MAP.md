# Route Map (Grouped by Blueprint)

Generated from `flask --app wsgi routes`.

## admin

- `GET       ` `/admin/`  →  `admin.dashboard`
- `GET       ` `/admin/moderation`  →  `admin.moderation`

### Users
- `GET       ` `/admin/users`  →  `admin.users`
- `POST      ` `/admin/users/<int:user_id>/toggle-active`  →  `admin.toggle_user_active`

### Services
- `GET       ` `/admin/services`  →  `admin.services`
- `POST      ` `/admin/services/<int:service_id>/toggle`  →  `admin.toggle_service`

### Bookings + Refunds
- `GET       ` `/admin/bookings`  →  `admin.bookings`
- `POST      ` `/admin/bookings/<int:booking_id>/force-cancel`  →  `admin.force_cancel_booking`
- `GET       ` `/admin/refunds`  →  `admin.refund_requests`
- `POST      ` `/admin/refunds/<int:booking_id>/decision`  →  `admin.decide_refund_request`

### Provider Verifications
- `GET       ` `/admin/verifications`  →  `admin.verifications`
- `POST      ` `/admin/verifications/<int:verification_id>/approve`  →  `admin.approve_verification`
- `POST      ` `/admin/verifications/<int:verification_id>/reject`  →  `admin.reject_verification`
- `POST      ` `/admin/verifications/<int:verification_id>/reset`  →  `admin.reset_verification`
- `GET       ` `/admin/verifications/<int:verification_id>/download/<string:kind>`  →  `admin.download_verification_doc`

## auth

- `GET, POST ` `/auth/login`  →  `auth.login`
- `GET       ` `/auth/logout`  →  `auth.logout`
- `GET, POST ` `/auth/register`  →  `auth.register`
- `GET, POST ` `/auth/forgot-password`  →  `auth.forgot_password`
- `GET, POST ` `/auth/reset-password/<token>`  →  `auth.reset_password`

## main

### Public
- `GET       ` `/`  →  `main.home`
- `GET       ` `/favicon.ico`  →  `main.favicon`
- `GET       ` `/health`  →  `main.health`
- `GET       ` `/services`  →  `main.services`
- `GET       ` `/services/<int:service_id>`  →  `main.service_detail`
- `GET       ` `/providers/<int:provider_id>`  →  `main.provider_public_profile`

### Booking flow
- `POST      ` `/services/<int:service_id>/book`  →  `main.book_service`
- `GET, POST ` `/checkout/<int:booking_id>`  →  `main.checkout`

### Client
- `GET       ` `/my/bookings`  →  `main.my_bookings`
- `POST      ` `/bookings/<int:booking_id>/cancel`  →  `main.cancel_booking`

### Provider helper routes on main blueprint
- `GET       ` `/provider/bookings`  →  `main.provider_bookings`
- `POST      ` `/provider/bookings/<int:booking_id>/status`  →  `main.update_booking_status`

### Provider time off + provider service actions on main blueprint
- `GET       ` `/provider/time-off`  →  `main.provider_time_off`
- `POST      ` `/provider/time-off/<int:time_off_id>/edit`  →  `main.edit_time_off`
- `POST      ` `/provider/time-off/<int:time_off_id>/delete`  →  `main.delete_time_off`

- `POST      ` `/provider/services/<int:service_id>/toggle`  →  `main.provider_toggle_service`
- `POST      ` `/provider/services/<int:service_id>/delete`  →  `main.provider_delete_service`
- `POST      ` `/provider/services/<int:service_id>/edit`  →  `main.provider_edit_service`

### Service requests + inquiries
- `GET, POST ` `/requests/new`  →  `main.request_service`
- `POST      ` `/services/<int:service_id>/inquiry`  →  `main.service_inquiry`

## messages

- `GET       ` `/messages/`  →  `messages.inbox`
- `GET, POST ` `/messages/<int:conversation_id>`  →  `messages.thread`
- `GET       ` `/messages/booking/<int:booking_id>`  →  `messages.booking_thread`

## provider

- `GET       ` `/provider/dashboard`  →  `provider.dashboard`
- `GET, POST ` `/provider/profile`  →  `provider.profile`
- `GET, POST ` `/provider/settings`  →  `provider.settings`
- `GET, POST ` `/provider/verification`  →  `provider.verification`

### Availability
- `GET, POST ` `/provider/availability`  →  `provider.availability`
- `POST      ` `/provider/availability/preset`  →  `provider.availability_preset`
- `POST      ` `/provider/availability/<int:rule_id>/update`  →  `provider.update_availability`
- `POST      ` `/provider/availability/<int:rule_id>/toggle`  →  `provider.toggle_availability`
- `POST      ` `/provider/availability/<int:rule_id>/delete`  →  `provider.delete_availability`

### Calendar + time off
- `GET       ` `/provider/calendar`  →  `provider.calendar_view`
- `GET, POST ` `/provider/time-off`  →  `provider.time_off`

### Service requests board (provider read-only)
- `GET       ` `/provider/requests`  →  `provider.requests_board`

## provider_services

- `GET       ` `/provider/services`  →  `provider_services.my_services`
- `GET, POST ` `/provider/services/new`  →  `provider_services.new_service`

## service_requests

### Client request history (route exists but may be disabled in final build)
- `GET       ` `/my/requests`  →  `service_requests.my_requests`
- `POST      ` `/my/requests/<int:request_id>/close`  →  `service_requests.close_request`

### Admin request moderation
- `GET       ` `/admin/requests`  →  `service_requests.admin_requests`
- `POST      ` `/admin/requests/<int:request_id>/close`  →  `service_requests.admin_close_request`

### Provider legacy endpoints (kept for backward compatibility)
- `GET       ` `/provider/requests-legacy`  →  `service_requests.provider_requests`
- `POST      ` `/provider/requests/<int:request_id>/claim`  →  `service_requests.claim_request`
- `POST      ` `/provider/requests/<int:request_id>/fulfill`  →  `service_requests.fulfill_request`

### Client submit (duplicate mapping)
- `GET, POST ` `/requests/new`  →  `service_requests.request_service`

## other
- `GET       ` `/static/<path:filename>`  →  `static`