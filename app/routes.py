"""
Main/public routes for ServiceSphere.

This blueprint handles the marketplace side of the app:
- home page + service browsing
- service detail + slot generation
- client booking + inquiry flows
- client session dashboard and checkout
- a few provider helper routes that live on the main blueprint

I keep most of the public workflow here so the role-specific blueprints
(provider/admin/messages) can stay focused.
"""

from datetime import datetime, timedelta, time
import secrets

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

from app.utils.flash import flash_success, flash_warning, flash_danger
from app.decorators import role_required
from app.extensions import db
from app.models import (
    User,
    Service,
    Booking,
    Message,
    ProviderProfile,
    ProviderAvailability,
    ProviderTimeOff,
    ServiceRequest,
)

main = Blueprint("main", __name__)


def _run_booking_housekeeping() -> None:
    """Runs lightweight booking cleanup that keeps the UI accurate.

    I call this from normal page routes instead of using a background job.
    The main thing it does is auto-cancel unpaid bookings that are too close
    to the session start time, so providers don't see stale pending sessions.
    """
    try:
        Booking.auto_cancel_unpaid_within_hours(hours=24)
    except Exception:
        # If this ever fails, I don't want it to take down normal page loads.
        # If I wanted extra visibility later, I could log current_app.logger.exception(...).
        pass


@main.route("/favicon.ico")
def favicon():
    """Serve favicon from the static folder."""
    return send_from_directory(current_app.static_folder, "favicon.ico")


def _hhmm_to_time(hhmm: str) -> time:
    """Convert a simple 'HH:MM' string into a datetime.time object."""
    h, m = hhmm.split(":")
    return time(hour=int(h), minute=int(m))


def generate_available_slots(service: Service, days_ahead: int = 7) -> list[datetime]:
    """Generate bookable slots for a service based on provider scheduling rules.

    What this returns:
    - UTC-naive datetimes (this matches how the rest of the project uses datetime.utcnow()).

    What this considers:
    - Provider weekly availability windows (ProviderAvailability)
    - Provider time off blocks (ProviderTimeOff)
    - Existing bookings that block time (pending + accepted)
    - Inquiry pseudo-bookings do not block time

    Key rules I enforce here:
    - Lead time: clients cannot book within the next 24 hours
    - Slots only show start times where the full service duration fits
    - Overlap detection uses the booking duration so it blocks correctly
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
    min_start = now + timedelta(hours=24)

    provider_user_id = provider_profile.user_id
    service_duration = int(getattr(service, "duration_minutes", 60) or 60)

    # I treat pending + accepted bookings as "busy" so we never double-book.
    # I ignore inquiry pseudo-bookings because they aren’t real scheduled sessions.
    busy = (
        Booking.query
        .filter_by(provider_id=provider_user_id)
        .filter(Booking.status.in_([Booking.STATUS_PENDING, Booking.STATUS_ACCEPTED]))
        .filter((Booking.provider_note.is_(None)) | (~Booking.provider_note.like("[INQUIRY]%")))
        .all()
    )

    busy_intervals: list[tuple[datetime, datetime]] = []
    for b in busy:
        start = b.booking_datetime.replace(second=0, microsecond=0)
        dur = int(getattr(b, "duration_minutes", 60) or 60)
        end = start + timedelta(minutes=dur)
        busy_intervals.append((start, end))

    # Time off acts like another kind of "busy interval".
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
        dow = day.weekday()

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

            # I only offer start times where the full service fits inside the availability window.
            while cursor + timedelta(minutes=service_duration) <= end_dt:
                candidate = cursor.replace(second=0, microsecond=0)
                candidate_end = candidate + timedelta(minutes=service_duration)

                # Lead-time rule: no same-day / last-minute booking.
                if candidate >= min_start:
                    blocked = any(overlaps(candidate, candidate_end, bs, be) for (bs, be) in busy_intervals)
                    if not blocked:
                        slots.append(candidate)

                cursor += timedelta(minutes=slot_minutes)

    slots.sort()
    return slots[:500]


@main.route("/")
def home():
    """Landing page."""
    return render_template("home.html")


@main.route("/services")
def services():
    """Public marketplace list view with search/filter/sort."""
    # I support both param names so older links don't break.
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
        "services/services_public.html",
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
        "provider/public_profile.html",
        provider=provider,
        profile=profile,
    )

@main.route("/services/<int:service_id>")
def service_detail(service_id: int):
    # Auto-cancel unpaid bookings that are now within 24h of start
    Booking.auto_cancel_unpaid_within_hours(hours=24)

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
        "services/service_detail.html",
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

    selected = (request.form.get("booking_datetime") or "").strip()
    if not selected:
        flash("Please select a booking time.", "danger")
        return redirect(url_for("main.service_detail", service_id=service.id))

    try:
        booking_dt = datetime.fromisoformat(selected).replace(second=0, microsecond=0)
    except ValueError:
        flash("Invalid booking time format.", "danger")
        return redirect(url_for("main.service_detail", service_id=service.id))

    now = datetime.utcnow().replace(second=0, microsecond=0)

    if booking_dt < now:
        flash("That time is in the past. Please choose another slot.", "warning")
        return redirect(url_for("main.service_detail", service_id=service.id))

    # ✅ Hard lead-time rule: clients must book at least 24 hours in advance
    min_start = now + timedelta(hours=24)
    if booking_dt < min_start:
        flash("Bookings must be scheduled at least 24 hours in advance.", "warning")
        return redirect(url_for("main.service_detail", service_id=service.id))

    provider_user_id = service.provider_profile.user_id
    duration_minutes = int(getattr(service, "duration_minutes", 60) or 60)

        # ✅ Server-side hard block: prevent double-booking even if two clients click at once
    if Booking.has_time_conflict(
        provider_id=provider_user_id,
        start_dt=booking_dt,
        duration_minutes=duration_minutes,
    ):
        flash("That time slot is no longer available. Please choose another slot.", "warning")
        return redirect(url_for("main.service_detail", service_id=service.id))

    # ✅ Client cannot book overlapping sessions (even with different providers/services)
    if Booking.client_has_time_conflict(
        client_id=current_user.id,
        start_dt=booking_dt,
        duration_minutes=duration_minutes,
    ):
        flash("You already have a booking at this time. Please choose a different time.", "warning")
        return redirect(url_for("main.service_detail", service_id=service.id))


    # Ensure selected slot is still available (UI consistency)
    # Note: use 21 days here to match service_detail’s calendar window
    available = generate_available_slots(service, days_ahead=21)
    available_set = {dt.replace(second=0, microsecond=0) for dt in available}
    if booking_dt not in available_set:
        flash("That time is no longer available. Please choose another slot.", "warning")
        return redirect(url_for("main.service_detail", service_id=service.id))

    # ✅ KEY FIX: reuse existing inquiry booking to avoid a second thread
    inquiry = (
        Booking.query.filter_by(
            client_id=current_user.id,
            provider_id=provider_user_id,
            service_id=service.id,
        )
        .filter(Booking.provider_note.isnot(None))
        .filter(Booking.provider_note.like("[INQUIRY]%"))
        .order_by(Booking.created_at.desc())
        .first()
    )

    if inquiry:
        # Convert inquiry booking into a real booking (same booking id => same conversation/thread)
        inquiry.booking_datetime = booking_dt
        inquiry.duration_minutes = duration_minutes
        inquiry.status = Booking.STATUS_PENDING

        # Remove inquiry marker so it behaves like a normal booking
        inquiry.provider_note = None

        # Reset payment fields if present
        if hasattr(inquiry, "payment_status"):
            inquiry.payment_status = "unpaid"
            inquiry.paid_at = None
            inquiry.payment_reference = None

        if hasattr(inquiry, "decided_at"):
            inquiry.decided_at = None

        db.session.commit()

        flash(
            "Booking requested! Proceed to checkout (demo) to confirm, then message the provider.",
            "success",
        )
        return redirect(url_for("main.checkout", booking_id=inquiry.id))

    # Otherwise create a new booking as normal
    booking = Booking(
        provider_id=provider_user_id,
        client_id=current_user.id,
        service_id=service.id,
        booking_datetime=booking_dt,
        duration_minutes=duration_minutes,
        status=Booking.STATUS_PENDING,
    )

    if hasattr(booking, "payment_status"):
        booking.payment_status = "unpaid"

    db.session.add(booking)
    db.session.commit()

    flash(
        "Booking requested! Proceed to checkout (demo) to confirm, then message the provider.",
        "success",
    )
    return redirect(url_for("main.checkout", booking_id=booking.id))


@main.route("/checkout/<int:booking_id>", methods=["GET", "POST"])
@login_required
def checkout(booking_id: int):
    booking = Booking.query.get_or_404(booking_id)

    # Block checkout for cancelled/declined/completed/refunded OR refund-pending sessions (server-side safety)
    note = (booking.admin_note or "")

    is_refunded = (getattr(booking, "payment_status", "") == "refunded") or ("[REFUND_APPROVED]" in note)
    is_refund_pending = note.startswith("[REFUND_REQUEST]")
    is_past_state = (booking.status or "").lower() in ["cancelled", "declined", "completed"]

    if is_refunded or is_refund_pending or is_past_state:
        if is_refunded:
            msg = "Checkout is not available for refunded sessions."
        elif is_refund_pending:
            msg = "Checkout is disabled while a refund request is pending review."
        else:
            msg = "Checkout is not available for cancelled/declined/completed sessions."

        flash(msg, "warning")
        return redirect(url_for("main.my_bookings"))

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

    return render_template("bookings/checkout.html", booking=booking)

# ---- Client service requests (MVP) ----
@main.route("/requests/new", methods=["GET", "POST"])
@login_required
@role_required("client")
def request_service():
    if request.method == "POST":
        subject = (request.form.get("subject") or "").strip()
        description = (request.form.get("description") or "").strip()

        if not subject or not description:
            flash_warning("Subject and description are required.")
            return render_template("client/requests_new.html")

        if len(subject) > 150:
            flash_warning("Subject is too long (max 150 characters).")
            return render_template("client/requests_new.html")

        sr = ServiceRequest(
            client_id=current_user.id,
            subject=subject,
            description=description,
            status="open",
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        db.session.add(sr)
        db.session.commit()

        flash_success("Service request submitted. An admin will review it.")
        return redirect(url_for("main.services"))

    return render_template("client/requests_new.html")

# ---- Client bookings ----
@main.route("/my/bookings")
@login_required
@role_required("client")
def my_bookings():
    # Auto-cancel unpaid bookings that are now within 24h of start
    Booking.auto_cancel_unpaid_within_hours(hours=24)

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
    return render_template("client/my_bookings.html", bookings=bookings)


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


@main.route("/provider/time-off", methods=["GET"])
@login_required
@role_required("provider")
def provider_time_off():
    profile = ProviderProfile.query.filter_by(user_id=current_user.id).first()

    if not profile:
        flash_warning("Create your provider profile first.")
        return redirect(url_for("provider.profile"))

    time_off_entries = (
        ProviderTimeOff.query
        .filter_by(provider_profile_id=profile.id)
        .order_by(ProviderTimeOff.start_datetime.desc())
        .all()
    )

    return render_template(
        "provider/time_off.html",
        entries=time_off_entries
    )

@main.route("/provider/time-off/<int:time_off_id>/delete", methods=["POST"])
@login_required
@role_required("provider")
def delete_time_off(time_off_id: int):
    entry = ProviderTimeOff.query.get_or_404(time_off_id)

    profile = ProviderProfile.query.filter_by(user_id=current_user.id).first()
    if not profile or entry.provider_profile_id != profile.id:
        abort(403)

    db.session.delete(entry)
    db.session.commit()

    flash_success("Time off entry deleted.")
    return redirect(url_for("main.provider_time_off"))


@main.route("/provider/time-off/<int:time_off_id>/edit", methods=["POST"])
@login_required
@role_required("provider")
def edit_time_off(time_off_id: int):
    entry = ProviderTimeOff.query.get_or_404(time_off_id)

    profile = ProviderProfile.query.filter_by(user_id=current_user.id).first()
    if not profile or entry.provider_profile_id != profile.id:
        abort(403)

    all_day = bool(request.form.get("all_day"))
    start_date = request.form.get("start_date")
    end_date = request.form.get("end_date")
    start_time = request.form.get("start_time")
    end_time = request.form.get("end_time")
    reason = (request.form.get("reason") or "").strip()

    try:
        start_dt = datetime.strptime(start_date, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date, "%Y-%m-%d")

        if not all_day:
            st = datetime.strptime(start_time, "%H:%M").time()
            et = datetime.strptime(end_time, "%H:%M").time()

            start_dt = datetime.combine(start_dt.date(), st)
            end_dt = datetime.combine(end_dt.date(), et)
        else:
            start_dt = datetime.combine(start_dt.date(), datetime.min.time())
            end_dt = datetime.combine(end_dt.date(), datetime.max.time())

    except Exception:
        flash_warning("Invalid date/time values.")
        return redirect(url_for("main.provider_time_off"))

    now = datetime.utcnow()

# 🚫 Prevent time-off that is entirely in the past
    if end_dt <= now:
        flash_warning("You cannot block time that has already passed.")
        return redirect(url_for("main.provider_time_off"))

    if end_dt <= start_dt:
        flash_warning("End must be after start.")
        return redirect(url_for("main.provider_time_off"))

    entry.start_datetime = start_dt
    entry.end_datetime = end_dt
    entry.all_day = all_day
    entry.reason = reason or None

    db.session.commit()

    flash_success("Time off updated.")
    return redirect(url_for("main.provider_time_off"))

# ---- Provider bookings ----
@main.route("/provider/bookings")
@login_required
@role_required("provider")
def provider_bookings():
    # Auto-cancel unpaid bookings that are now within 24h of start
    Booking.auto_cancel_unpaid_within_hours(hours=24)

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
    return render_template("provider/bookings.html", bookings=bookings)

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