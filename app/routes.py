# app/routes.py
from datetime import datetime, timedelta, time
import secrets
from app.utils.flash import flash_success, flash_warning, flash_danger

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    abort,
    send_from_directory,
    current_app,
)

from flask_login import login_required, current_user

from app.decorators import role_required
from app.extensions import db
from app.models import User, Service, Booking, Message, ProviderProfile, ProviderAvailability, ProviderTimeOff

main = Blueprint("main", __name__)


@main.route("/favicon.ico")
def favicon():
    return send_from_directory(current_app.static_folder, "favicon.ico")


def _hhmm_to_time(hhmm: str) -> time:
    # hhmm like "15:00"
    h, m = hhmm.split(":")
    return time(hour=int(h), minute=int(m))


def generate_available_slots(service: Service, days_ahead: int = 7) -> list[datetime]:
    """
    Returns UTC-naive datetimes (consistent with your current utcnow usage).
    Slots are generated from provider availability windows and filtered by existing bookings.

    Blocking rules:
      - accepted always blocks
      - pending blocks only if created within last 30 minutes (anti-spam hold)
      - overlap-aware (uses booking duration_minutes)
      - provider time off blocks (vacation/partial blocks)

    Lead time rule:
      - clients cannot book sooner than 24 hours from now
    """
    provider_profile = service.provider_profile
    if not provider_profile:
        return []

    rules = (
        ProviderAvailability.query
        .filter_by(provider_profile_id=provider_profile.id, is_active=True)
        .all()
    )
    if not rules:
        return []

    now = datetime.utcnow().replace(second=0, microsecond=0)
    min_start = now + timedelta(hours=24)  # <-- lead time enforcement

    provider_user_id = provider_profile.user_id
    pending_hold_minutes = 30
    pending_cutoff = now - timedelta(minutes=pending_hold_minutes)

    busy = (
        Booking.query
        .filter_by(provider_id=provider_user_id)
        .filter(
            (Booking.status == "accepted") |
            ((Booking.status == "pending") & (Booking.created_at >= pending_cutoff))
        )
        .all()
    )

    # Build busy intervals: [start, end)
    busy_intervals: list[tuple[datetime, datetime]] = []

    # 1) Existing bookings (accepted + recent pending holds)
    for b in busy:
        start = b.booking_datetime.replace(second=0, microsecond=0)
        dur = int(getattr(b, "duration_minutes", 60) or 60)
        end = start + timedelta(minutes=dur)
        busy_intervals.append((start, end))

    # 2) Provider time off (vacation / blocked periods)
    window_start = now
    window_end = now + timedelta(days=days_ahead + 1)

    time_off_entries = (
        ProviderTimeOff.query
        .filter_by(provider_profile_id=provider_profile.id)
        .filter(ProviderTimeOff.end_datetime > window_start)
        .filter(ProviderTimeOff.start_datetime < window_end)
        .all()
    )

    for e in time_off_entries:
        start = e.start_datetime.replace(second=0, microsecond=0)
        end = e.end_datetime.replace(second=0, microsecond=0)
        busy_intervals.append((start, end))

    def overlaps(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
        return a_start < b_end and a_end > b_start

    slots: list[datetime] = []

    for day_offset in range(days_ahead + 1):
        day = (now + timedelta(days=day_offset)).date()
        dow = day.weekday()  # 0=Mon..6=Sun

        day_rules = [r for r in rules if r.day_of_week == dow]
        if not day_rules:
            continue

        for r in day_rules:
            start_t = _hhmm_to_time(r.start_time)
            end_t = _hhmm_to_time(r.end_time)
            slot_minutes = int(r.slot_minutes or 30)

            start_dt = datetime.combine(day, start_t)
            end_dt = datetime.combine(day, end_t)

            cursor = start_dt
            while cursor + timedelta(minutes=slot_minutes) <= end_dt:
                candidate = cursor.replace(second=0, microsecond=0)
                candidate_end = candidate + timedelta(minutes=slot_minutes)

                # Enforce: no slots within the next 24 hours
                if candidate >= min_start:
                    blocked = any(overlaps(candidate, candidate_end, bs, be) for (bs, be) in busy_intervals)
                    if not blocked:
                        slots.append(candidate)

                cursor += timedelta(minutes=slot_minutes)

    slots.sort()
    # Cap slots to avoid rendering huge pages, but allow ~3 weeks of 30-min slots
    return slots[:500]


@main.route("/")
def home():
    return render_template("home.html")


@main.route("/services")
def services():
    # Support both param names:
    # - new UI uses q
    # - older links may still use search
    search = (request.args.get("q") or request.args.get("search") or "").strip()
    category = (request.args.get("category") or "").strip()
    sort = (request.args.get("sort") or "").strip()

    query = Service.query.filter(Service.is_active.is_(True))

    if search:
        query = query.filter(
            (Service.title.ilike(f"%{search}%")) |
            (Service.description.ilike(f"%{search}%"))
        )

    if category:
        query = query.filter(Service.category == category)

    # Sorting (no schema changes)
    if sort == "price_low":
        query = query.order_by(Service.price.asc(), Service.created_at.desc())
    elif sort == "price_high":
        query = query.order_by(Service.price.desc(), Service.created_at.desc())
    elif sort == "title_az":
        query = query.order_by(Service.title.asc(), Service.created_at.desc())
    else:
        # default: newest first (current behavior)
        query = query.order_by(Service.created_at.desc())

    services = query.all()

    # Categories for pills (only from visible services so the UI matches inventory)
    categories = (
        db.session.query(Service.category)
        .filter(Service.is_active.is_(True))
        .filter(Service.category.isnot(None))
        .distinct()
        .all()
    )
    categories = [c[0] for c in categories]

    return render_template(
        "services_public.html",
        services=services,
        categories=categories,
        selected_category=category,
        search=search,
        sort=sort,
    )

@main.get("/providers/<int:provider_id>")
def provider_public_profile(provider_id: int):
    provider = User.query.get_or_404(provider_id)

    # Only allow viewing real providers
    if not provider.has_role("provider"):
        abort(404)

    profile = getattr(provider, "provider_profile", None)

    return render_template(
        "provider_public_profile.html",
        provider=provider,
        profile=profile,
    )

@main.route("/services/<int:service_id>")
def service_detail(service_id: int):
    service = Service.query.get_or_404(service_id)

    # Block hidden services from public view (admins + owning provider may still view)
    if not service.is_active:
        is_admin = current_user.is_authenticated and current_user.has_role("admin")
        is_owner_provider = (
            current_user.is_authenticated
            and current_user.has_role("provider")
            and service.provider_profile
            and service.provider_profile.user_id == current_user.id
        )
        if not (is_admin or is_owner_provider):
            abort(404)

    has_active_booking = False
    active_status = None

    # Only relevant for logged-in clients
    if current_user.is_authenticated and current_user.has_role("client"):
        existing = (
            Booking.query
            .filter_by(client_id=current_user.id, service_id=service.id)
            .filter(Booking.status.in_(["pending", "accepted"]))
            .first()
        )
        if existing:
            has_active_booking = True
            active_status = existing.status

    # Scheduling: compute slots for next 30 days (used by template)
    available_slots = generate_available_slots(service, days_ahead=21)

    return render_template(
        "service_detail.html",
        service=service,
        has_active_booking=has_active_booking,
        active_status=active_status,
        available_slots=available_slots,
    )

@main.route("/services/<int:service_id>/inquiry", methods=["POST"])
@login_required
@role_required("client")
def service_inquiry(service_id: int):
    """
    Pre-book inquiry messaging without schema changes.

    Implementation strategy:
      - Reuse Booking + Conversation + Message (no new tables)
      - Create a special "inquiry booking" (tagged) to anchor the conversation
      - Rate limit: 1 inquiry per (client, service) per 24 hours
      - Use far-future booking_datetime placeholder to satisfy NOT NULL constraint
    """
    service = Service.query.get_or_404(service_id)

    # Block inquiries for hidden services
    if not service.is_active:
        abort(404)

    body = (request.form.get("message") or "").strip()
    if not body:
        flash("Please enter a message.", "warning")
        return redirect(url_for("main.service_detail", service_id=service.id))

    if len(body) > 500:
        flash("Message is too long (max 500 characters).", "warning")
        return redirect(url_for("main.service_detail", service_id=service.id))

    now = datetime.utcnow()
    cutoff = now - timedelta(hours=24)

    inquiry_prefix = "[INQUIRY]"
    existing = (
        Booking.query
        .filter_by(client_id=current_user.id, service_id=service.id)
        .filter(Booking.created_at >= cutoff)
        .filter(Booking.provider_note.isnot(None))
        .filter(Booking.provider_note.ilike(f"{inquiry_prefix}%"))
        .order_by(Booking.created_at.desc())
        .first()
    )

    if existing:
        convo = existing.get_or_create_conversation()
        flash("You already sent an inquiry for this service recently. Continuing that thread.", "info")
        return redirect(url_for("messages.booking_thread", booking_id=existing.id, _anchor="compose"))

    # Create an "inquiry booking" to anchor a conversation (no schema changes)
    provider_user_id = service.provider_profile.user_id

    inquiry_booking = Booking(
        provider_id=provider_user_id,
        client_id=current_user.id,
        service_id=service.id,
        # Placeholder datetime (far future) to satisfy NOT NULL.
        # We'll hide these from the Sessions dashboard in a later micro-step.
        booking_datetime=datetime(2099, 1, 1, 0, 0, 0),
        duration_minutes=0,
        status=Booking.STATUS_PENDING,
        payment_status="unpaid",
        provider_note=f"{inquiry_prefix} Pre-book inquiry",
    )

    db.session.add(inquiry_booking)
    db.session.commit()

    convo = inquiry_booking.get_or_create_conversation()

    msg = Message(
        conversation_id=convo.id,
        sender_id=current_user.id,
        body=body,
    )
    db.session.add(msg)
    db.session.commit()

    flash("Inquiry sent to the provider.", "success")
    return redirect(url_for("messages.booking_thread", booking_id=inquiry_booking.id, _anchor="compose"))


@main.route("/services/<int:service_id>/book", methods=["POST"])
@login_required
@role_required("client")
def book_service(service_id: int):
    service = Service.query.get_or_404(service_id)

    # Prevent booking hidden/inactive services
    if not service.is_active:
        abort(404)

    # Read selected slot from form (ISO string)
    selected = (request.form.get("booking_datetime") or "").strip()
    if not selected:
        flash("Please select a booking time.", "danger")
        return redirect(url_for("main.service_detail", service_id=service.id))

    # Parse ISO datetime safely (expects "YYYY-MM-DDTHH:MM" or with seconds)
    try:
        booking_dt = datetime.fromisoformat(selected)
        booking_dt = booking_dt.replace(second=0, microsecond=0)
    except ValueError:
        flash("Invalid booking time format.", "danger")
        return redirect(url_for("main.service_detail", service_id=service.id))

    # Reject past times
    now = datetime.utcnow().replace(second=0, microsecond=0)
    if booking_dt < now:
        flash("That time is in the past. Please choose another slot.", "warning")
        return redirect(url_for("main.service_detail", service_id=service.id))

    # Race-condition safety: ensure the selected slot is still available
    available = generate_available_slots(service, days_ahead=7)
    available_set = {dt.replace(second=0, microsecond=0) for dt in available}
    if booking_dt not in available_set:
        flash("That time is no longer available. Please choose another slot.", "warning")
        return redirect(url_for("main.service_detail", service_id=service.id))

    provider_user_id = service.provider_profile.user_id

    # ✅ KEY FIX: if an inquiry booking exists for this same client/provider/service,
    # convert it into the real booking instead of creating a second booking (and second thread).
    inquiry = Booking.find_open_inquiry(
        client_id=current_user.id,
        provider_id=provider_user_id,
        service_id=service.id,
    )

    if inquiry:
        # Convert inquiry booking into a real booking
        inquiry.booking_datetime = booking_dt
        inquiry.duration_minutes = 60
        inquiry.status = Booking.STATUS_PENDING

        # Ensure inquiry marker is removed so it shows in Sessions dashboard
        inquiry.provider_note = None

        # If your model has payment_status, reset it explicitly (safe)
        if hasattr(inquiry, "payment_status"):
            inquiry.payment_status = "unpaid"
            inquiry.paid_at = None
            inquiry.payment_reference = None

        # clear decision timestamps if present
        if hasattr(inquiry, "decided_at"):
            inquiry.decided_at = None

        db.session.commit()

        flash("Booking requested! Proceed to checkout (demo) to confirm, then message the provider.", "success")
        return redirect(url_for("main.checkout", booking_id=inquiry.id))

    # Otherwise create a new booking as normal
    booking = Booking(
        provider_id=provider_user_id,
        client_id=current_user.id,
        service_id=service.id,
        booking_datetime=booking_dt,
        duration_minutes=60,
        status=Booking.STATUS_PENDING,
    )

    # If your model has payment_status, set explicitly (safe)
    if hasattr(booking, "payment_status"):
        booking.payment_status = "unpaid"

    db.session.add(booking)
    db.session.commit()

    flash("Booking requested! Proceed to checkout (demo) to confirm, then message the provider.", "success")
    return redirect(url_for("main.checkout", booking_id=booking.id))

@main.route("/checkout/<int:booking_id>", methods=["GET", "POST"])
@login_required
def checkout(booking_id: int):
    booking = Booking.query.get_or_404(booking_id)

    # Only booking participants can access checkout (admins too)
    is_admin = current_user.is_authenticated and current_user.has_role("admin")
    if (current_user.id not in (booking.client_id, booking.provider_id)) and not is_admin:
        abort(403)

    if request.method == "POST":
        # ---- Demo checkout validation (do not store payment info) ----
        payment_method = (request.form.get("payment_method") or "").strip().lower()

        if payment_method not in {"card", "paypal", "applepay"}:
            flash("Please select a payment method.", "danger")
            return redirect(url_for("main.checkout", booking_id=booking.id))

        if payment_method == "card":
            card_name = (request.form.get("card_name") or "").strip()
            card_number = (request.form.get("card_number") or "").strip().replace(" ", "")
            card_exp = (request.form.get("card_exp") or "").strip()
            card_cvc = (request.form.get("card_cvc") or "").strip()

            # Basic demo checks (NOT real payment validation)
            if not card_name:
                flash("Name on card is required (demo).", "danger")
                return redirect(url_for("main.checkout", booking_id=booking.id))

            if not (card_number.isdigit() and 12 <= len(card_number) <= 19):
                flash("Card number looks invalid (demo).", "danger")
                return redirect(url_for("main.checkout", booking_id=booking.id))

            # Expect MM/YY
            if len(card_exp) != 5 or card_exp[2] != "/":
                flash("Expiration must be in MM/YY format (demo).", "danger")
                return redirect(url_for("main.checkout", booking_id=booking.id))
            mm, yy = card_exp.split("/", 1)
            if not (mm.isdigit() and yy.isdigit() and 1 <= int(mm) <= 12 and len(yy) == 2):
                flash("Expiration looks invalid (demo).", "danger")
                return redirect(url_for("main.checkout", booking_id=booking.id))

            if not (card_cvc.isdigit() and 3 <= len(card_cvc) <= 4):
                flash("CVC looks invalid (demo).", "danger")
                return redirect(url_for("main.checkout", booking_id=booking.id))

        # Mark as paid (demo) after validation
        if booking.payment_status != "paid":
            booking.payment_status = "paid"
            booking.paid_at = datetime.utcnow()
            booking.payment_reference = f"demo_{secrets.token_hex(6)}"

            # Make persistence explicit + verifiable
            db.session.add(booking)
            db.session.commit()

            # Sanity: prove DB actually has it
            db.session.expire_all()
            refreshed = Booking.query.get(booking.id)
            flash(f"Payment successful (demo). Status now: {refreshed.payment_status}", "success")
        else:
            flash("This booking is already marked as paid.", "info")

        # After paying, jump into the booking's message thread
        return redirect(
            url_for("messages.booking_thread", booking_id=booking.id, _anchor="compose")
        )

    return render_template("checkout.html", booking=booking)

# ---- Client bookings ----
@main.route("/my/bookings")
@login_required
@role_required("client")
def my_bookings():
    # Hide inquiry-only "pseudo bookings" from the Sessions dashboard.
    # Inquiries are still accessible via Messages.
    inquiry_prefix = "[INQUIRY]"

    bookings = (
        Booking.query
        .filter(Booking.client_id == current_user.id)
        .filter(
            (Booking.provider_note.is_(None)) |
            (~Booking.provider_note.ilike(f"{inquiry_prefix}%"))
        )
        .order_by(Booking.created_at.desc())
        .all()
    )
    return render_template("my_bookings.html", bookings=bookings)

# ---- Client cancel / refund request ----
@main.route("/bookings/<int:booking_id>/cancel", methods=["POST"])
@login_required
@role_required("client")
def cancel_booking(booking_id: int):
    booking = Booking.query.get_or_404(booking_id)

    # Ownership check
    if booking.client_id != current_user.id:
        flash_danger("You are not authorized to modify this booking.")
        return redirect(url_for("main.my_bookings"))

    # Never allow actions on inquiry pseudo-bookings from Sessions
    if (booking.provider_note or "").startswith("[INQUIRY]"):
        flash_warning("This is an inquiry thread, not a booked session.")
        return redirect(url_for("main.my_bookings"))

    # If UNPAID: allow true cancel (pending or accepted)
    if booking.payment_status != "paid":
        # expand beyond strict state machine: allow cancel for pending/accepted unpaid
        if (booking.status or "").lower() not in (Booking.STATUS_PENDING, Booking.STATUS_ACCEPTED):
            flash_warning(f"Cannot cancel a booking that is already '{booking.status}'.")
            return redirect(url_for("main.my_bookings", _anchor=f"booking-{booking.id}"))

        booking.status = Booking.STATUS_CANCELLED
        booking.decided_at = datetime.utcnow()
        db.session.commit()

        flash_success("Booking cancelled.")
        return redirect(url_for("main.my_bookings", _anchor=f"booking-{booking.id}"))

    # If PAID: do NOT change status (no refund status exists) — create refund request record
    reason = (request.form.get("refund_reason") or "").strip()
    if len(reason) > 500:
        flash_warning("Refund reason is too long (max 500 characters).")
        return redirect(url_for("main.my_bookings", _anchor=f"booking-{booking.id}"))

    tag = "[REFUND_REQUEST]"
    note = f"{tag} {reason}" if reason else f"{tag} Client requested refund/cancel."

    # Store in existing admin moderation fields (no ERD changes)
    booking.admin_note = note
    booking.admin_action_at = datetime.utcnow()
    db.session.commit()

    flash_success("Refund requested. You’ll be notified once it’s reviewed.")
    return redirect(url_for("main.my_bookings", _anchor=f"booking-{booking.id}"))


# ---- Provider bookings ----
@main.route("/provider/bookings")
@login_required
@role_required("provider")
def provider_bookings():
    profile = ProviderProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        flash("Create your provider profile before viewing bookings.", "warning")
        return redirect(url_for("provider.profile"))

    bookings = (
        Booking.query
        .filter_by(provider_id=current_user.id)
        .order_by(Booking.created_at.desc())
        .all()
    )
    return render_template("provider_bookings.html", bookings=bookings)


# ---- Provider can update booking status ----
@main.route("/provider/bookings/<int:booking_id>/status", methods=["POST"])
@login_required
@role_required("provider")
def update_booking_status(booking_id: int):
    booking = Booking.query.get_or_404(booking_id)

    # Ownership check: only assigned provider can modify
    if booking.provider_id != current_user.id:
        flash_danger("You are not authorized to modify this booking.")
        return redirect(url_for("main.provider_bookings"))

    # Guard: provider cannot accept/decline until client has paid (demo checkout)
    if booking.payment_status != "paid":
        flash_warning(
            "This booking must be paid before you can accept or decline it (demo checkout)."
        )
        return redirect(url_for("main.provider_bookings", _anchor=f"booking-{booking.id}"))

    new_status = (request.form.get("status") or "").strip().lower()

    # Providers are only allowed to accept/decline
    provider_allowed = {Booking.STATUS_ACCEPTED, Booking.STATUS_DECLINED}
    if new_status not in provider_allowed:
        flash_danger("Invalid status update.")
        return redirect(url_for("main.provider_bookings", _anchor=f"booking-{booking.id}"))

    # Enforce model-defined state transitions
    if not booking.can_transition_to(new_status):
        flash_warning(f"Cannot change a booking that is already '{booking.status}'.")
        return redirect(url_for("main.provider_bookings", _anchor=f"booking-{booking.id}"))

    # Save decision + optional note
    booking.status = new_status
    booking.decided_at = datetime.utcnow()
    booking.provider_note = (request.form.get("provider_note") or "").strip() or None

    db.session.commit()

    flash_success(f"Booking {new_status}.")
    return redirect(url_for("main.provider_bookings", _anchor=f"booking-{booking.id}"))

# ---- Provider services (manage) ----
@main.route("/provider/services/<int:service_id>/delete", methods=["POST"])
@login_required
@role_required("provider")
def provider_delete_service(service_id: int):
    service = Service.query.get_or_404(service_id)

    # Ownership check
    if not service.provider_profile or service.provider_profile.user_id != current_user.id:
        flash_danger("You are not authorized to delete this service.")
        return redirect(url_for("provider_services.my_services"))

    # IMPORTANT: If *any* bookings exist, we cannot delete without breaking FK integrity
    # (bookings.service_id is NOT NULL). Preserve history.
    has_any_bookings = (
        Booking.query.filter_by(service_id=service.id).first() is not None
    )
    if has_any_bookings:
        flash_warning("This service has booking history and can’t be deleted. Hide it instead.")
        return redirect(url_for("provider_services.my_services"))

    db.session.delete(service)
    db.session.commit()
    flash_success("Service deleted.")
    return redirect(url_for("provider_services.my_services"))

@main.route("/provider/services/<int:service_id>/toggle", methods=["POST"])
@login_required
@role_required("provider")
def provider_toggle_service(service_id: int):
    service = Service.query.get_or_404(service_id)

    # Ownership check
    if not service.provider_profile or service.provider_profile.user_id != current_user.id:
        flash_danger("You are not authorized to update this service.")
        return redirect(url_for("provider_services.my_services"))

    # If currently hidden, unhide is only allowed if it wasn't admin-moderated.
    # We treat moderation_note as the "admin action reason" flag.
    if not bool(service.is_active):
        if service.moderation_note:
            flash_warning("This service was hidden by an admin and can’t be unhidden here.")
            return redirect(url_for("provider_services.my_services"))

        service.is_active = True
        db.session.commit()
        flash_success("Service is now visible to clients.")
        return redirect(url_for("provider_services.my_services"))

    # If currently active, providers can always hide their own service
    service.is_active = False
    db.session.commit()
    flash_success("Service hidden.")
    return redirect(url_for("provider_services.my_services"))

# ---- Health check (deployment / proxy verification) ----
@main.get("/health")
def health():
    """
    Lightweight health endpoint.
    Useful for confirming the app is reachable through a proxy (or locally via curl).
    """
    return {
        "status": "ok",
        "utc": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }, 200


@main.route("/provider/services/<int:service_id>/edit", methods=["POST"])
@login_required
@role_required("provider")
def provider_edit_service(service_id):
    service = Service.query.get_or_404(service_id)

    if not service.provider_profile or service.provider_profile.user_id != current_user.id:
        flash_danger("Not authorized.")
        return redirect(url_for("provider_services.my_services"))

    service.title = request.form.get("title")
    service.description = request.form.get("description")
    service.price = float(request.form.get("price") or 0)

    db.session.commit()

    flash_success("Service updated.")
    return redirect(url_for("provider_services.my_services"))