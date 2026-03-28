# app/provider.py
from datetime import datetime, timedelta
import os

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app.extensions import db
from app.decorators import role_required
from app.models import ProviderProfile, ProviderAvailability

provider = Blueprint("provider", __name__, url_prefix="/provider")

def _allowed_upload(filename: str) -> bool:
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    allowed = current_app.config.get("ALLOWED_UPLOAD_EXTENSIONS", set())
    return ext in allowed


def _save_verification_file(file_storage, provider_profile_id: int, kind: str) -> str | None:
    """
    Save an uploaded file to instance/uploads/verification/.
    Returns stored filename (relative name only), or None if no file.
    """
    if not file_storage or not getattr(file_storage, "filename", ""):
        return None

    original = file_storage.filename
    if not _allowed_upload(original):
        raise ValueError("Invalid file type. Allowed: PDF, PNG, JPG, JPEG.")

    safe = secure_filename(original)
    ext = safe.rsplit(".", 1)[1].lower()

    # Create folder instance/uploads/verification
    base_dir = current_app.config["UPLOAD_DIR"]
    target_dir = os.path.join(str(base_dir), "verification")
    os.makedirs(target_dir, exist_ok=True)

    # Deterministic-ish unique name per submit
    ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    stored = f"provider_{provider_profile_id}_{kind}_{ts}.{ext}"

    file_storage.save(os.path.join(target_dir, stored))
    return stored

@provider.route("/dashboard")
@login_required
@role_required("provider")
def dashboard():
    return render_template("provider_dashboard.html")


@provider.route("/verification", methods=["GET", "POST"])
@login_required
@role_required("provider")
def verification():
    """
    Provider submits verification info.
    Workflow: unverified/rejected -> pending_review
    """
    profile = ProviderProfile.query.filter_by(user_id=current_user.id).first_or_404()

    # Ensure a verification row exists
    verification = profile.get_or_create_verification()

    if request.method == "POST":
        # Only allow submission if not already pending/verified
        if verification.status in ("pending_review", "verified"):
            flash("Your verification is already in progress or completed.", "info")
            return redirect(url_for("provider.verification"))

        legal_name = (request.form.get("legal_name") or "").strip()
        license_number = (request.form.get("license_number") or "").strip()
        portfolio_url = (request.form.get("portfolio_url") or "").strip()

                # Optional uploads
        try:
            id_doc = _save_verification_file(request.files.get("id_document"), profile.id, "id")
            cert_doc = _save_verification_file(request.files.get("certification"), profile.id, "cert")
        except ValueError as e:
            flash(str(e), "danger")
            return redirect(url_for("provider.verification"))

        if id_doc:
            verification.id_document_filename = id_doc
        if cert_doc:
            verification.certification_filename = cert_doc

        verification.legal_name = legal_name or None
        verification.license_number = license_number or None
        verification.portfolio_url = portfolio_url or None

        verification.status = "pending_review"
        verification.submitted_at = datetime.utcnow()
        verification.admin_notes = None  # clear old notes on resubmit
        verification.reviewed_at = None
        verification.reviewed_by_admin_id = None

        db.session.commit()
        flash("Verification submitted! Status: pending review.", "success")
        return redirect(url_for("provider.verification"))

    return render_template(
    "provider/provider_verification.html",
    profile=profile,
    verification=verification,
)

@provider.route("/profile", methods=["GET", "POST"])
@login_required
@role_required("provider")
def profile():
    # One-to-one: each provider has at most one ProviderProfile
    profile = ProviderProfile.query.filter_by(user_id=current_user.id).first()

    if request.method == "GET":
        return render_template("provider_profile.html", profile=profile)

    # POST: create or update
    bio = (request.form.get("bio") or "").strip()
    hourly_rate_raw = (request.form.get("hourly_rate") or "").strip()
    availability_notes = (request.form.get("availability_notes") or "").strip()

    # Minimal validation (keep it simple for Phase 1.3)
    if not bio:
        flash("Bio is required.", "danger")
        return redirect(url_for("provider.profile"))

    hourly_rate = None
    if hourly_rate_raw:
        try:
            hourly_rate = float(hourly_rate_raw)
            if hourly_rate < 0:
                raise ValueError()
        except ValueError:
            flash("Hourly rate must be a valid non-negative number.", "danger")
            return redirect(url_for("provider.profile"))

    if profile is None:
        profile = ProviderProfile(
            user_id=current_user.id,
            bio=bio,
            hourly_rate=hourly_rate,
            availability_notes=availability_notes or None,
        )
        db.session.add(profile)
        flash("Provider profile created.", "success")
    else:
        profile.bio = bio
        profile.hourly_rate = hourly_rate
        profile.availability_notes = availability_notes or None
        flash("Provider profile updated.", "success")

    db.session.commit()
    return redirect(url_for("provider.profile"))


@provider.route("/availability", methods=["GET", "POST"])
@login_required
@role_required("provider")
def availability():
    profile = ProviderProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        flash("Create your provider profile before setting availability.", "warning")
        return redirect(url_for("provider.profile"))
    
        # Auto-create default availability (Mon–Fri 9am–5pm) if provider has no rules yet
    existing_count = ProviderAvailability.query.filter_by(provider_profile_id=profile.id).count()
    if existing_count == 0:
        default_days = [0, 1, 2, 3, 4]  # Mon-Fri (matches your day_of_week convention)
        for dow in default_days:
            db.session.add(ProviderAvailability(
                provider_profile_id=profile.id,
                day_of_week=dow,
                start_time="09:00",
                end_time="17:00",
                slot_minutes=60,
                is_active=True,
                created_at=datetime.utcnow(),
            ))
        db.session.commit()
        flash("Default availability created (Mon–Fri 9:00 AM–5:00 PM). You can edit it anytime.", "info")

    if request.method == "POST":
        try:
            day_of_week = int(request.form.get("day_of_week"))
        except (TypeError, ValueError):
            flash("Invalid day selection.", "danger")
            return redirect(url_for("provider.availability"))

        start_time = (request.form.get("start_time") or "").strip()
        end_time = (request.form.get("end_time") or "").strip()

        try:
            slot_minutes = int(request.form.get("slot_minutes") or 30)
        except (TypeError, ValueError):
            slot_minutes = 30

        if day_of_week not in range(0, 7):
            flash("Invalid day selection.", "danger")
            return redirect(url_for("provider.availability"))

        if not start_time or not end_time:
            flash("Start and end time are required.", "danger")
            return redirect(url_for("provider.availability"))

        # Basic validation: HH:MM and start < end (lexicographic works for 24h HH:MM)
        if len(start_time) != 5 or len(end_time) != 5 or start_time >= end_time:
            flash("Invalid time window. Use HH:MM and ensure start < end.", "danger")
            return redirect(url_for("provider.availability"))

        if slot_minutes < 15 or slot_minutes > 240 or (slot_minutes % 15 != 0):
            flash("Slot minutes must be between 15 and 240, in 15-minute increments.", "danger")
            return redirect(url_for("provider.availability"))

        rule = ProviderAvailability(
            provider_profile_id=profile.id,
            day_of_week=day_of_week,
            start_time=start_time,
            end_time=end_time,
            slot_minutes=slot_minutes,
            is_active=True,
            created_at=datetime.utcnow(),
        )
        db.session.add(rule)
        db.session.commit()

        flash("Availability window added.", "success")
        return redirect(url_for("provider.availability"))

    rules = (
        ProviderAvailability.query
        .filter_by(provider_profile_id=profile.id)
        .order_by(ProviderAvailability.day_of_week.asc(), ProviderAvailability.start_time.asc())
        .all()
    )
    return render_template("provider_availability.html", rules=rules)


@provider.route("/availability/<int:rule_id>/delete", methods=["POST"])
@login_required
@role_required("provider")
def delete_availability(rule_id: int):

    profile = ProviderProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        flash("Create your provider profile first.", "warning")
        return redirect(url_for("provider.profile"))

    rule = ProviderAvailability.query.get_or_404(rule_id)
    if rule.provider_profile_id != profile.id:
        flash("Not authorized to modify this availability.", "danger")
        return redirect(url_for("provider.availability"))

    db.session.delete(rule)
    db.session.commit()
    flash("Availability window removed.", "success")
    return redirect(url_for("provider.availability"))

@provider.route("/availability/<int:rule_id>/toggle", methods=["POST"])
@login_required
@role_required("provider")
def toggle_availability(rule_id: int):
    profile = ProviderProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        flash("Create your provider profile first.", "warning")
        return redirect(url_for("provider.profile"))

    rule = ProviderAvailability.query.get_or_404(rule_id)
    if rule.provider_profile_id != profile.id:
        flash("Not authorized to modify this availability.", "danger")
        return redirect(url_for("provider.availability"))

    rule.is_active = not bool(rule.is_active)
    db.session.commit()

    flash(f"Availability {'enabled' if rule.is_active else 'disabled'}.", "success")
    return redirect(url_for("provider.availability"))

@provider.route("/calendar")
@login_required
@role_required("provider")
def calendar_view():
    profile = ProviderProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        flash("Create your provider profile before viewing calendar.", "warning")
        return redirect(url_for("provider.profile"))

    # Use local "now" for UI shading expectations (per project notes)
    now_local = datetime.now().replace(second=0, microsecond=0)
    today_local = now_local.date()

    # --- Week selection (Sunday-start like Google week view) ---
    week_str = (request.args.get("week") or "").strip()

    try:
        selected = datetime.strptime(week_str, "%Y-%m-%d").date() if week_str else today_local
    except ValueError:
        selected = today_local

    # Sunday-start week
    # Python: Monday=0..Sunday=6. Convert to Sunday-start offset.
    sunday_offset = (selected.weekday() + 1) % 7
    week_start = selected - timedelta(days=sunday_offset)
    week_end = week_start + timedelta(days=7)  # exclusive

    week_days = [week_start + timedelta(days=i) for i in range(7)]

    # Pull availability rules (active only)
    rules = (
        ProviderAvailability.query
        .filter_by(provider_profile_id=profile.id, is_active=True)
        .order_by(ProviderAvailability.day_of_week.asc(), ProviderAvailability.start_time.asc())
        .all()
    )

    # Bookings for this provider within the selected week (pending + accepted)
    from app.models import Booking, ProviderTimeOff

    week_start_dt = datetime.combine(week_start, datetime.min.time())
    week_end_dt = datetime.combine(week_end, datetime.min.time())

    bookings = (
        Booking.query
        .filter(Booking.provider_id == current_user.id)
        .filter(Booking.status.in_(["pending", "accepted"]))
        .filter(Booking.booking_datetime >= week_start_dt)
        .filter(Booking.booking_datetime < week_end_dt)
        .order_by(Booking.booking_datetime.asc())
        .all()
    )

    # Time off entries overlapping this week
    time_off_entries = (
        ProviderTimeOff.query
        .filter_by(provider_profile_id=profile.id)
        .filter(ProviderTimeOff.end_datetime > week_start_dt)
        .filter(ProviderTimeOff.start_datetime < week_end_dt)
        .order_by(ProviderTimeOff.start_datetime.asc())
        .all()
    )

    return render_template(
        "provider_calendar.html",
        rules=rules,
        bookings=bookings,
        time_off_entries=time_off_entries,
        week_start=week_start,
        week_days=week_days,
        timedelta=timedelta,
        now_local=now_local,
    )

@provider.route("/time-off", methods=["GET", "POST"])
@login_required
@role_required("provider")
def time_off():
    profile = ProviderProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        flash("Create your provider profile before managing time off.", "warning")
        return redirect(url_for("provider.profile"))

    from app.models import ProviderTimeOff

    # --- Prefill defaults from query params (GET) ---
    prefill = {
        "all_day": False,
        "start_date": "",
        "end_date": "",
        "start_time": "09:00",
        "end_time": "17:00",
        "reason": "",
    }

    start_q = (request.args.get("start") or "").strip()  # YYYY-MM-DDTHH:MM
    end_q = (request.args.get("end") or "").strip()      # YYYY-MM-DDTHH:MM

    def _parse_iso_local(s: str):
        # Expect "YYYY-MM-DDTHH:MM"
        return datetime.strptime(s, "%Y-%m-%dT%H:%M")

    if start_q and end_q:
        try:
            sdt = _parse_iso_local(start_q)
            edt = _parse_iso_local(end_q)
            if edt > sdt:
                prefill["start_date"] = sdt.strftime("%Y-%m-%d")
                prefill["end_date"] = edt.strftime("%Y-%m-%d")
                prefill["start_time"] = sdt.strftime("%H:%M")
                prefill["end_time"] = edt.strftime("%H:%M")
        except ValueError:
            # Ignore bad query params; fall back to defaults
            pass

    if request.method == "POST":
        # Inputs
        all_day = (request.form.get("all_day") == "on")
        start_date = (request.form.get("start_date") or "").strip()   # YYYY-MM-DD
        end_date = (request.form.get("end_date") or "").strip()       # YYYY-MM-DD
        start_time = (request.form.get("start_time") or "09:00").strip()  # HH:MM
        end_time = (request.form.get("end_time") or "17:00").strip()      # HH:MM
        reason = (request.form.get("reason") or "").strip() or None

        if not start_date or not end_date:
            flash("Start date and end date are required.", "danger")
            return redirect(url_for("provider.time_off"))

        try:
            if all_day:
                start_dt = datetime.strptime(start_date, "%Y-%m-%d")
                # end at 23:59 on end_date
                end_dt = datetime.strptime(end_date + " 23:59", "%Y-%m-%d %H:%M")
            else:
                start_dt = datetime.strptime(start_date + " " + start_time, "%Y-%m-%d %H:%M")
                end_dt = datetime.strptime(end_date + " " + end_time, "%Y-%m-%d %H:%M")
        except ValueError:
            flash("Invalid date/time format.", "danger")
            return redirect(url_for("provider.time_off"))

        if end_dt <= start_dt:
            flash("End must be after start.", "danger")
            return redirect(url_for("provider.time_off"))

        entry = ProviderTimeOff(
            provider_profile_id=profile.id,
            start_datetime=start_dt,
            end_datetime=end_dt,
            all_day=all_day,
            reason=reason,
        )
        db.session.add(entry)
        db.session.commit()
        flash("Time off saved.", "success")
        return redirect(url_for("provider.time_off"))

    entries = (
        ProviderTimeOff.query
        .filter_by(provider_profile_id=profile.id)
        .order_by(ProviderTimeOff.start_datetime.desc())
        .all()
    )

    # Pass defaults so template can prefill inputs
    return render_template("provider_time_off.html", entries=entries, prefill=prefill)

@provider.route("/availability/preset", methods=["POST"])
@login_required
@role_required("provider")
def availability_preset():
    profile = ProviderProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        flash("Create your provider profile before setting availability.", "warning")
        return redirect(url_for("provider.profile"))

    preset = (request.form.get("preset") or "").strip()

    def add_window(dow: int, start: str, end: str, slot: int = 30):
        db.session.add(ProviderAvailability(
            provider_profile_id=profile.id,
            day_of_week=dow,
            start_time=start,
            end_time=end,
            slot_minutes=slot,
            is_active=True,
            created_at=datetime.utcnow(),
        ))

    if preset == "mon_fri_9_5":
        for dow in range(0, 5):  # Mon..Fri
            add_window(dow, "09:00", "17:00", 30)
        db.session.commit()
        flash("Preset added: Mon–Fri 9:00–17:00 (30-min slots).", "success")
        return redirect(url_for("provider.availability"))

    flash("Unknown preset.", "danger")
    return redirect(url_for("provider.availability"))