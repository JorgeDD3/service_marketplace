# app/admin.py
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
from .models import User, Service, Booking, ServiceRequest, ProviderVerification

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


@admin_bp.route("/")
@login_required
@role_required("admin")
def dashboard():
    # Admin moderation hub is the primary "dashboard" now
    return redirect(url_for("admin.moderation"))


# app/admin.py

@admin_bp.route("/moderation")
@login_required
@role_required("admin")
def moderation():
    """
    Admin moderation hub.
    Shows "needs attention" counts.
    """

    # Pending verification submissions
    pending_verifications = ProviderVerification.query.filter_by(
        status="pending_review"
    ).count()

    # Open service requests (client requests)
    open_service_requests = ServiceRequest.query.filter_by(
        status="open"
    ).count()

    # Hidden services (not active)
    hidden_services = Service.query.filter(Service.is_active.is_(False)).count()

    # Disabled users
    disabled_users = User.query.filter(User.is_active.is_(False)).count()

    # Refund requests (SAFE: do not assume schema fields exist)
    refund_requests = 0
    if hasattr(Booking, "refund_requested"):
        refund_requests = Booking.query.filter(Booking.refund_requested.is_(True)).count()
    elif hasattr(Booking, "client_requested_refund"):
        refund_requests = Booking.query.filter(Booking.client_requested_refund.is_(True)).count()
    elif hasattr(Booking, "status"):
        refund_requests = Booking.query.filter(
            Booking.status.in_(["refund_requested", "refund_request"])
        ).count()

    notif = {
        "refund_requests": refund_requests,
        "pending_verifications": pending_verifications,
        "open_service_requests": open_service_requests,
        "hidden_services": hidden_services,
        "disabled_users": disabled_users,
    }

    return render_template("admin/admin_moderation.html", notif=notif)

# --------------------
# Users (Admin Moderation)
# --------------------

@admin_bp.route("/users")
@login_required
@role_required("admin")
def users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=users)


@admin_bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@login_required
@role_required("admin")
def toggle_user_active(user_id: int):
    target = User.query.get_or_404(user_id)

    # Guardrail 1: admin cannot disable themself
    if target.id == current_user.id:
        flash("You cannot disable your own account.", "danger")
        return redirect(url_for("admin.users"))

    # Guardrail 2: do not disable the last remaining admin
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

    # Toggle
    if target.is_active:
        # disable
        target.is_active = False
        target.disabled_at = datetime.utcnow()
        reason = (request.form.get("disabled_reason") or "").strip()
        target.disabled_reason = reason or "Disabled by admin"
        flash(f"User {target.email} disabled.", "success")
    else:
        # enable
        target.is_active = True
        target.disabled_at = None
        target.disabled_reason = None
        flash(f"User {target.email} enabled.", "success")

    db.session.commit()
    return redirect(url_for("admin.users"))


# --------------------
# Services (Admin Moderation)
# --------------------

@admin_bp.route("/services")
@login_required
@role_required("admin")
def services():
    services = Service.query.order_by(Service.created_at.desc()).all()
    return render_template("admin/services.html", services=services)


@admin_bp.route("/services/<int:service_id>/toggle", methods=["POST"])
@login_required
@role_required("admin")
def toggle_service(service_id: int):
    svc = Service.query.get_or_404(service_id)

    action = (request.form.get("action") or "toggle").strip().lower()
    note = (request.form.get("moderation_note") or "").strip()

    # Always allow updating the note (including clearing it)
    svc.moderation_note = note or None
    svc.moderated_at = datetime.utcnow()

    # Only toggle visibility when explicitly requested
    if action == "toggle":
        svc.is_active = not bool(svc.is_active)

    db.session.commit()

    if action == "save":
        flash("Moderation note saved.", "success")
    else:
        flash(f"Service {'activated' if svc.is_active else 'hidden'}.", "success")

    return redirect(url_for("admin.services"))


# --------------------
# Bookings (Admin Moderation)
# --------------------

@admin_bp.route("/bookings")
@login_required
@role_required("admin")
def bookings():
    bookings = Booking.query.order_by(Booking.created_at.desc()).all()
    return render_template("admin/bookings.html", bookings=bookings)

@admin_bp.route("/refund-requests")
@login_required
@role_required("admin")
def refund_requests():
    """
    Dedicated admin view for refund/cancel requests.
    Template-only page (links into bookings for action).
    """
    return render_template("admin/refund_requests.html")


@admin_bp.route("/bookings/<int:booking_id>/force-cancel", methods=["POST"])
@login_required
@role_required("admin")
def force_cancel_booking(booking_id: int):
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


# --------------------
# Provider Verifications (Admin Review Queue)
# --------------------

@admin_bp.route("/verifications")
@login_required
@role_required("admin")
def verifications():
    pending = (
        ProviderVerification.query
        .filter_by(status="pending_review")
        .order_by(
            ProviderVerification.submitted_at.asc().nullslast(),
            ProviderVerification.created_at.asc()
        )
        .all()
    )

    reviewed = (
        ProviderVerification.query
        .filter(ProviderVerification.status.in_(["verified", "rejected"]))
        .order_by(
            ProviderVerification.reviewed_at.desc().nullslast(),
            ProviderVerification.updated_at.desc()
        )
        .limit(20)
        .all()
    )

    return render_template("admin/verifications.html", pending=pending, reviewed=reviewed)


@admin_bp.route("/verifications/<int:verification_id>/approve", methods=["POST"])
@login_required
@role_required("admin")
def approve_verification(verification_id: int):
    v = ProviderVerification.query.get_or_404(verification_id)

    if v.status != "pending_review":
        flash("Only pending verifications can be approved.", "warning")
        return redirect(url_for("admin.verifications"))

    v.status = "verified"
    v.reviewed_at = datetime.utcnow()
    v.reviewed_by_admin_id = current_user.id
    v.admin_notes = (request.form.get("admin_notes") or "").strip() or None

    db.session.commit()
    flash("Provider verification approved.", "success")
    return redirect(url_for("admin.verifications"))


@admin_bp.route("/verifications/<int:verification_id>/reject", methods=["POST"])
@login_required
@role_required("admin")
def reject_verification(verification_id: int):
    v = ProviderVerification.query.get_or_404(verification_id)

    if v.status != "pending_review":
        flash("Only pending verifications can be rejected.", "warning")
        return redirect(url_for("admin.verifications"))

    notes = (request.form.get("admin_notes") or "").strip()
    if not notes:
        flash("Rejection requires admin notes (reason).", "danger")
        return redirect(url_for("admin.verifications"))

    v.status = "rejected"
    v.reviewed_at = datetime.utcnow()
    v.reviewed_by_admin_id = current_user.id
    v.admin_notes = notes

    db.session.commit()
    flash("Provider verification rejected.", "success")
    return redirect(url_for("admin.verifications"))


# --------------------
# Provider Verification Document Download (Admin-only)
# --------------------

@admin_bp.route("/verifications/<int:verification_id>/download/<string:kind>")
@login_required
@role_required("admin")
def download_verification_doc(verification_id: int, kind: str):
    """
    Admin-only download for verification documents.
    kind: 'id' or 'cert'
    """
    v = ProviderVerification.query.get_or_404(verification_id)

    if kind not in ("id", "cert"):
        abort(404)

    filename = v.id_document_filename if kind == "id" else v.certification_filename
    if not filename:
        abort(404)

    # Prevent path traversal / weird filenames
    if "/" in filename or "\\" in filename or ".." in filename:
        abort(400)

    base_dir = current_app.config.get("UPLOAD_DIR")
    if not base_dir:
        abort(500)

    folder = os.path.join(str(base_dir), "verification")
    return send_from_directory(folder, filename, as_attachment=True)