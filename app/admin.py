# app/admin.py
"""
Admin blueprint for ServiceSphere.

This module contains admin-only moderation tooling:
- moderation hub with "needs attention" counts
- user enable/disable (with guardrails)
- service hide/unhide + moderation notes
- booking console + force-cancel
- refund request queue + decision workflow
- provider verification queue + document downloads

All admin routes require login + the admin role.
"""

from datetime import datetime
import os

from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app,
    send_from_directory,
    abort,
)
from flask_login import login_required, current_user

from .decorators import role_required
from .extensions import db
from .models import Booking, ProviderProfile, ProviderVerification, Service, ServiceRequest, User

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
@login_required
@role_required("admin")
def dashboard():
    """Admin entry route.

    I keep /admin/ as a stable link and redirect it to the moderation hub.
    """
    return redirect(url_for("admin.moderation"))


@admin_bp.route("/moderation")
@login_required
@role_required("admin")
def moderation():
    """Admin moderation hub.

    Shows high-level counts so an admin knows what to triage first.
    """
    pending_verifications = ProviderVerification.query.filter_by(status="pending_review").count()
    open_service_requests = ServiceRequest.query.filter_by(status="open").count()
    hidden_services = Service.query.filter(Service.is_active.is_(False)).count()
    disabled_users = User.query.filter(User.is_active.is_(False)).count()

    # Refund requests are modeled via tags in Booking.admin_note (no ERD changes).
    refund_requests = Booking.query.filter(
        Booking.admin_note.ilike("%[REFUND_REQUEST]%"),
        ~Booking.admin_note.ilike("%[REFUND_APPROVED]%"),
        ~Booking.admin_note.ilike("%[REFUND_DENIED]%"),
    ).count()

    notif = {
        "refund_requests": refund_requests,
        "pending_verifications": pending_verifications,
        "open_service_requests": open_service_requests,
        "hidden_services": hidden_services,
        "disabled_users": disabled_users,
    }

    return render_template("admin/moderation.html", notif=notif)


@admin_bp.route("/users")
@login_required
@role_required("admin")
def users():
    """User moderation list (enable/disable)."""
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=users)


@admin_bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@login_required
@role_required("admin")
def toggle_user_active(user_id: int):
    """Enable/disable a user account.

    Guardrails:
    - admins cannot disable themselves
    - the last active admin cannot be disabled

    Side effect (provider only):
    - when a provider is disabled, active services are auto-hidden and tagged
    - when re-enabled, only tagged services are restored
    """
    target = User.query.get_or_404(user_id)
    auto_marker = "[AUTO_DISABLED_BY_USER]"

    # Guardrail: admin cannot disable themself.
    if target.id == current_user.id:
        flash("You cannot disable your own account.", "danger")
        return redirect(url_for("admin.users"))

    # Guardrail: do not disable the last remaining admin.
    is_target_admin = target.has_role("admin")
    if is_target_admin and target.is_active:
        active_admin_count = (
            User.query.join(User.role)
            .filter_by(role_name="admin")
            .filter(User.is_active.is_(True))
            .count()
        )
        if active_admin_count <= 1:
            flash("You cannot disable the last active admin.", "danger")
            return redirect(url_for("admin.users"))

    # Resolve services owned by this provider in a schema-tolerant way.
    services_q = None
    provider_profile_id = None

    if target.has_role("provider"):
        provider_profile_id = (
            ProviderProfile.query.with_entities(ProviderProfile.id)
            .filter(ProviderProfile.user_id == target.id)
            .scalar()
        )

        if hasattr(Service, "user_id"):
            services_q = Service.query.filter(Service.user_id == target.id)
        elif provider_profile_id is not None and hasattr(Service, "provider_profile_id"):
            services_q = Service.query.filter(Service.provider_profile_id == provider_profile_id)
        elif provider_profile_id is not None and hasattr(Service, "provider_id"):
            # Some schemas name it provider_id but store ProviderProfile.id.
            services_q = Service.query.filter(Service.provider_id == provider_profile_id)

    if target.is_active:
        # Disable user.
        target.is_active = False
        target.disabled_at = datetime.utcnow()
        reason = (request.form.get("disabled_reason") or "").strip()
        target.disabled_reason = reason or "Disabled by admin"

        # Auto-hide only active services and tag them so we can restore safely later.
        if services_q is not None:
            active_services = services_q.filter(Service.is_active.is_(True)).all()
            for svc in active_services:
                svc.is_active = False

                note = (svc.moderation_note or "").strip()
                if auto_marker not in note:
                    svc.moderation_note = (note + ("\n" if note else "") + auto_marker).strip()

                if hasattr(svc, "moderated_at"):
                    svc.moderated_at = datetime.utcnow()

        flash(f"User {target.email} disabled.", "success")
    else:
        # Enable user.
        target.is_active = True
        target.disabled_at = None
        target.disabled_reason = None

        # Restore only services that were auto-hidden by this workflow (marker-based).
        if services_q is not None:
            disabled_services = services_q.filter(Service.is_active.is_(False)).all()
            for svc in disabled_services:
                note = svc.moderation_note or ""
                if auto_marker in note:
                    svc.is_active = True

                    new_note = note.replace(auto_marker, "").strip()
                    svc.moderation_note = new_note or None

                    if hasattr(svc, "moderated_at"):
                        svc.moderated_at = datetime.utcnow()

        flash(f"User {target.email} enabled.", "success")

    db.session.commit()
    return redirect(url_for("admin.users"))


@admin_bp.route("/services")
@login_required
@role_required("admin")
def services():
    """Service moderation list (hide/unhide + notes)."""
    services = Service.query.order_by(Service.created_at.desc()).all()
    return render_template("admin/services.html", services=services)


@admin_bp.route("/services/<int:service_id>/toggle", methods=["POST"])
@login_required
@role_required("admin")
def toggle_service(service_id: int):
    """Update a service moderation note and optionally toggle visibility."""
    svc = Service.query.get_or_404(service_id)

    action = (request.form.get("action") or "toggle").strip().lower()
    note = (request.form.get("moderation_note") or "").strip()

    # Always allow updating the note (including clearing it).
    svc.moderation_note = note or None
    svc.moderated_at = datetime.utcnow()

    # Only toggle visibility when explicitly requested.
    if action == "toggle":
        svc.is_active = not bool(svc.is_active)

    db.session.commit()

    if action == "save":
        flash("Moderation note saved.", "success")
    else:
        flash(f"Service {'activated' if svc.is_active else 'hidden'}.", "success")

    return redirect(url_for("admin.services"))


@admin_bp.route("/bookings")
@login_required
@role_required("admin")
def bookings():
    """Bookings console (search/filter happens client-side in the template)."""
    bookings = Booking.query.order_by(Booking.created_at.desc()).all()
    return render_template("admin/bookings.html", bookings=bookings)


@admin_bp.route("/refunds")
@login_required
@role_required("admin")
def refund_requests():
    """Refund request queue.

    A booking appears here when Booking.admin_note contains [REFUND_REQUEST].
    Supports search across booking id, service title, client/provider emails, and note.
    """
    from sqlalchemy import cast, or_
    from sqlalchemy.types import String

    q = (request.args.get("q") or "").strip()

    # Base query: avoid joining User twice (SQLite ambiguity). Use relationship filters for emails.
    query = (
        Booking.query.outerjoin(Service, Booking.service_id == Service.id)
        .filter(Booking.admin_note.ilike("%[REFUND_REQUEST]%"))
    )

    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                cast(Booking.id, String).ilike(like),
                Service.title.ilike(like),
                Booking.admin_note.ilike(like),
                Booking.client.has(User.email.ilike(like)),
                Booking.provider.has(User.email.ilike(like)),
                cast(Booking.client_id, String).ilike(like),
                cast(Booking.provider_id, String).ilike(like),
            )
        )

    total = query.count()
    bookings = (
        query.order_by(
            Booking.admin_action_at.desc().nullslast(),
            Booking.created_at.desc(),
        )
        .all()
    )

    return render_template("admin/refund_requests.html", bookings=bookings, total=total, q=q)


@admin_bp.route("/refunds/<int:booking_id>/decision", methods=["POST"])
@login_required
@role_required("admin")
def decide_refund_request(booking_id: int):
    """Approve/deny a refund request using existing fields/tags (no ERD changes)."""
    booking = Booking.query.get_or_404(booking_id)

    current_note = (booking.admin_note or "").strip()
    if "[REFUND_REQUEST]" not in current_note:
        flash("This booking does not have an open refund request.", "warning")
        return redirect(url_for("admin.refund_requests"))

    decision = (request.form.get("decision") or "").strip().lower()
    admin_reason = (request.form.get("admin_reason") or "").strip()

    if decision not in {"approve", "deny"}:
        flash("Invalid refund decision.", "danger")
        return redirect(url_for("admin.refund_requests"))

    if not admin_reason:
        flash("Admin decision note is required.", "danger")
        return redirect(url_for("admin.refund_requests"))

    # Prevent double-processing.
    if decision == "approve" and "[REFUND_APPROVED]" in current_note:
        flash("This refund request was already approved.", "warning")
        return redirect(url_for("admin.refund_requests"))
    if decision == "deny" and "[REFUND_DENIED]" in current_note:
        flash("This refund request was already denied.", "warning")
        return redirect(url_for("admin.refund_requests"))

    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    if decision == "approve":
        # Cancel booking if still active so it drops out of “upcoming” views.
        if getattr(booking, "status", None) in ["pending", "accepted"]:
            booking.status = "cancelled"

        # Mark payment as refunded if the schema has payment_status.
        if hasattr(booking, "payment_status"):
            booking.payment_status = "refunded"

        decision_line = f"[REFUND_APPROVED] {timestamp} — {admin_reason}"
        flash_message = "Refund request approved and marked as refunded."
    else:
        decision_line = f"[REFUND_DENIED] {timestamp} — {admin_reason}"
        flash_message = "Refund request denied."

    booking.admin_note = current_note + ("\n" if current_note else "") + decision_line

    if hasattr(booking, "admin_action_at"):
        booking.admin_action_at = datetime.utcnow()
    if hasattr(booking, "decided_at"):
        booking.decided_at = datetime.utcnow()

    db.session.commit()
    flash(flash_message, "success")
    return redirect(url_for("admin.refund_requests"))


@admin_bp.route("/bookings/<int:booking_id>/force-cancel", methods=["POST"])
@login_required
@role_required("admin")
def force_cancel_booking(booking_id: int):
    """Force-cancel a pending/accepted booking (admin intervention)."""
    booking = Booking.query.get_or_404(booking_id)

    if booking.status not in ["pending", "accepted"]:
        flash(f"Cannot force-cancel a booking that is '{booking.status}'.", "warning")
        return redirect(url_for("admin.bookings"))

    booking.status = "cancelled"
    booking.admin_note = (request.form.get("admin_note") or "").strip() or None
    booking.admin_action_at = datetime.utcnow()

    db.session.commit()

    flash("Booking force-cancelled by admin.", "success")
    return redirect(url_for("admin.bookings"))


@admin_bp.route("/verifications")
@login_required
@role_required("admin")
def verifications():
    """Provider verification queue (pending + recent reviewed)."""
    pending = (
        ProviderVerification.query.filter_by(status="pending_review")
        .order_by(
            ProviderVerification.submitted_at.asc().nullslast(),
            ProviderVerification.created_at.asc(),
        )
        .all()
    )

    reviewed = (
        ProviderVerification.query.filter(ProviderVerification.status.in_(["verified", "rejected"]))
        .order_by(
            ProviderVerification.reviewed_at.desc().nullslast(),
            ProviderVerification.updated_at.desc(),
        )
        .limit(20)
        .all()
    )

    return render_template("admin/verifications.html", pending=pending, reviewed=reviewed)


@admin_bp.route("/verifications/<int:verification_id>/approve", methods=["POST"])
@login_required
@role_required("admin")
def approve_verification(verification_id: int):
    """Mark a provider verification as verified."""
    v = ProviderVerification.query.get_or_404(verification_id)

    v.status = "verified"
    v.reviewed_at = datetime.utcnow()
    v.reviewed_by_admin_id = current_user.id
    v.admin_notes = (request.form.get("admin_notes") or "").strip() or None

    db.session.commit()
    flash("Provider verification marked as verified.", "success")
    return redirect(url_for("admin.verifications"))


@admin_bp.route("/verifications/<int:verification_id>/reject", methods=["POST"])
@login_required
@role_required("admin")
def reject_verification(verification_id: int):
    """Reject a provider verification (requires a reason)."""
    v = ProviderVerification.query.get_or_404(verification_id)

    notes = (request.form.get("admin_notes") or "").strip()
    if not notes:
        flash("Rejection requires admin notes (reason).", "danger")
        return redirect(url_for("admin.verifications"))

    v.status = "rejected"
    v.reviewed_at = datetime.utcnow()
    v.reviewed_by_admin_id = current_user.id
    v.admin_notes = notes

    db.session.commit()
    flash("Provider verification marked as rejected.", "success")
    return redirect(url_for("admin.verifications"))


@admin_bp.route("/verifications/<int:verification_id>/reset", methods=["POST"])
@login_required
@role_required("admin")
def reset_verification(verification_id: int):
    """Reset a reviewed verification back to pending_review."""
    v = ProviderVerification.query.get_or_404(verification_id)

    v.status = "pending_review"
    v.reviewed_at = None
    v.reviewed_by_admin_id = None

    db.session.commit()
    flash("Verification reset to pending review.", "success")
    return redirect(url_for("admin.verifications"))


@admin_bp.route("/verifications/<int:verification_id>/download/<string:kind>")
@login_required
@role_required("admin")
def download_verification_doc(verification_id: int, kind: str):
    """Admin-only download for verification documents.

    kind must be 'id' or 'cert'.
    """
    v = ProviderVerification.query.get_or_404(verification_id)

    if kind not in ("id", "cert"):
        abort(404)

    filename = v.id_document_filename if kind == "id" else v.certification_filename
    if not filename:
        abort(404)

    # Prevent path traversal / weird filenames.
    if "/" in filename or "\\" in filename or ".." in filename:
        abort(400)

    base_dir = current_app.config.get("UPLOAD_DIR")
    if not base_dir:
        abort(500)

    folder = os.path.join(str(base_dir), "verification")
    return send_from_directory(folder, filename, as_attachment=True)