# Route Map (Grouped by Blueprint)

Generated from `flask --app wsgi routes`.

## main

- `GET      ` `/`  →  `main.home`
- `GET      ` `/admin-only`  →  `main.admin_only`
- `GET      ` `/favicon.ico`  →  `main.favicon`
- `GET      ` `/my/bookings`  →  `main.my_bookings`
- `POST     ` `/my/bookings/<int:booking_id>/cancel`  →  `main.cancel_booking`
- `GET      ` `/provider/bookings`  →  `main.provider_bookings`
- `POST     ` `/provider/bookings/<int:booking_id>/status`  →  `main.update_booking_status`
- `GET      ` `/services`  →  `main.services`
- `GET      ` `/services/<int:service_id>`  →  `main.service_detail`
- `POST     ` `/services/<int:service_id>/book`  →  `main.book_service`

## auth

- `GET, POST` `/auth/login`  →  `auth.login`
- `GET      ` `/auth/logout`  →  `auth.logout`
- `GET, POST` `/auth/register`  →  `auth.register`

## provider

- `GET, POST` `/provider/availability`  →  `provider.availability`
- `POST     ` `/provider/availability/<int:rule_id>/delete`  →  `provider.delete_availability`
- `POST     ` `/provider/availability/<int:rule_id>/toggle`  →  `provider.toggle_availability`
- `POST     ` `/provider/availability/preset`  →  `provider.availability_preset`
- `GET, POST` `/provider/profile`  →  `provider.profile`

## provider_services

- `GET      ` `/provider/services`  →  `provider_services.my_services`
- `GET, POST` `/provider/services/new`  →  `provider_services.new_service`

## service_requests

- `GET      ` `/admin/requests`  →  `service_requests.admin_requests`
- `POST     ` `/admin/requests/<int:request_id>/close`  →  `service_requests.admin_close_request`
- `GET      ` `/my/requests`  →  `service_requests.my_requests`
- `POST     ` `/my/requests/<int:request_id>/close`  →  `service_requests.close_request`
- `GET      ` `/provider/requests`  →  `service_requests.provider_requests`
- `POST     ` `/provider/requests/<int:request_id>/claim`  →  `service_requests.claim_request`
- `POST     ` `/provider/requests/<int:request_id>/fulfill`  →  `service_requests.fulfill_request`
- `GET, POST` `/requests/new`  →  `service_requests.request_service`

## admin

- `GET      ` `/admin/`  →  `admin.dashboard`
- `GET      ` `/admin/bookings`  →  `admin.bookings`
- `POST     ` `/admin/bookings/<int:booking_id>/force-cancel`  →  `admin.force_cancel_booking`
- `GET      ` `/admin/services`  →  `admin.services`
- `POST     ` `/admin/services/<int:service_id>/toggle`  →  `admin.toggle_service`
- `GET      ` `/admin/users`  →  `admin.users`
- `POST     ` `/admin/users/<int:user_id>/toggle-active`  →  `admin.toggle_user_active`

## other

- `GET      ` `/static/<path:filename>`  →  `static`
