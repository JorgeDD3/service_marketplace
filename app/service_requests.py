from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from .extensions import db
from .decorators import role_required
from .models import ServiceRequest

service_requests_bp = Blueprint("service_requests", __name__)


@service_requests_bp.route("/requests/new", methods=["GET", "POST"])
@login_required
@role_required("client")
def request_service():
    """Client: submit a new service request (something not currently listed)."""
    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        description = request.form.get("description", "").strip()

        if not subject or not description:
            flash("Subject and description are required.", "warning")
            return redirect(url_for("service_requests.request_service"))

        # Prevent duplicate active requests with the same subject from the same client.
        existing = ServiceRequest.query.filter(
            ServiceRequest.client_id == current_user.id,
            ServiceRequest.subject.ilike(subject),
            ServiceRequest.status.in_(["open", "claimed"]),
        ).first()
        if existing:
            flash("You already have an active request with this subject.", "warning")
            return redirect(url_for("main.services"))

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

        flash("Service request submitted.", "success")
        return redirect(url_for("main.services"))

    return render_template("requests_new.html")


@service_requests_bp.route("/my/requests")
@login_required
@role_required("client")
def my_requests():
    """Client request history is intentionally disabled for the final submission."""
    abort(404)

@service_requests_bp.route("/my/requests/<int:request_id>/close", methods=["POST"])
@login_required
@role_required("client")
def close_request(request_id):
    """Client: close one of your service requests."""
    sr = ServiceRequest.query.get_or_404(request_id)

    if sr.client_id != current_user.id:
        abort(403)

    if sr.status not in ["open", "claimed"]:
        flash("Only open or claimed requests can be closed.", "warning")
        return redirect(url_for("service_requests.my_requests"))

    sr.status = "closed"
    sr.closed_at = datetime.utcnow()
    sr.updated_at = datetime.utcnow()
    db.session.commit()

    flash("Request closed.", "success")
    return redirect(url_for("service_requests.my_requests"))


@service_requests_bp.route("/provider/requests-legacy")
@login_required
@role_required("provider")
def provider_requests():
    """Legacy provider requests route.

    Kept temporarily so older links don't break. The provider blueprint owns the
    canonical requests page at /provider/requests.
    """
    return redirect(url_for("provider.requests_board"))


@service_requests_bp.route("/provider/requests/<int:request_id>/claim", methods=["POST"])
@login_required
@role_required("provider")
def claim_request(request_id):
    """Provider action disabled.

    Providers can view requests, but request lifecycle is admin-managed.
    """
    _sr = ServiceRequest.query.get_or_404(request_id)
    flash("Providers can view requests, but only admins can close them.", "info")
    return redirect(url_for("provider.requests_board"))


@service_requests_bp.route("/provider/requests/<int:request_id>/fulfill", methods=["POST"])
@login_required
@role_required("provider")
def fulfill_request(request_id):
    """Provider action disabled.

    Providers can view requests, but request lifecycle is admin-managed.
    """
    _sr = ServiceRequest.query.get_or_404(request_id)
    flash("Providers can view requests, but only admins can close them.", "info")
    return redirect(url_for("provider.requests_board"))


@service_requests_bp.route("/admin/requests")
@login_required
@role_required("admin")
def admin_requests():
    """Admin: review all client service requests."""
    reqs = ServiceRequest.query.order_by(ServiceRequest.created_at.desc()).all()
    return render_template("admin/requests.html", requests=reqs)


@service_requests_bp.route("/admin/requests/<int:request_id>/close", methods=["POST"])
@login_required
@role_required("admin")
def admin_close_request(request_id):
    """Admin: close a request (used when resolved or no longer relevant)."""
    sr = ServiceRequest.query.get_or_404(request_id)

    if sr.status in ["closed", "fulfilled"]:
        flash("Request is already closed/fulfilled.", "warning")
        return redirect(url_for("service_requests.admin_requests"))

    sr.status = "closed"
    sr.closed_at = datetime.utcnow()
    sr.updated_at = datetime.utcnow()
    db.session.commit()

    flash("Request closed by admin.", "success")
    return redirect(url_for("service_requests.admin_requests"))