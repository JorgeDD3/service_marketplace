from datetime import datetime

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from .extensions import db
from .decorators import role_required
from .models import ServiceRequest

service_requests_bp = Blueprint("service_requests", __name__)


# -----------------------
# Client routes
# -----------------------

@service_requests_bp.route("/requests/new", methods=["GET", "POST"])
@login_required
@role_required("client")
def request_service():
    if request.method == "POST":
        subject = request.form.get("subject", "").strip()
        description = request.form.get("description", "").strip()

        if not subject or not description:
            flash("Subject and description are required.", "warning")
            return redirect(url_for("service_requests.request_service"))

        # Optional (recommended): prevent duplicate active requests by same client
        existing = ServiceRequest.query.filter(
            ServiceRequest.client_id == current_user.id,
            ServiceRequest.subject.ilike(subject),
            ServiceRequest.status.in_(["open", "claimed"])
        ).first()
        if existing:
            flash("You already have an active request with this subject.", "warning")
            return redirect(url_for("service_requests.my_requests"))

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
        return redirect(url_for("service_requests.my_requests"))

    return render_template("requests_new.html")


@service_requests_bp.route("/my/requests")
@login_required
@role_required("client")
def my_requests():
    reqs = (
        ServiceRequest.query
        .filter_by(client_id=current_user.id)
        .order_by(ServiceRequest.created_at.desc())
        .all()
    )
    return render_template("my_requests.html", requests=reqs)


@service_requests_bp.route("/my/requests/<int:request_id>/close", methods=["POST"])
@login_required
@role_required("client")
def close_request(request_id):
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


# -----------------------
# Provider routes
# -----------------------

@service_requests_bp.route("/provider/requests")
@login_required
@role_required("provider")
def provider_requests():
    open_reqs = (
        ServiceRequest.query
        .filter_by(status="open")
        .order_by(ServiceRequest.created_at.desc())
        .all()
    )

    my_claimed = (
        ServiceRequest.query
        .filter_by(status="claimed", claimed_by_provider_id=current_user.id)
        .order_by(ServiceRequest.created_at.desc())
        .all()
    )

    return render_template(
        "provider_requests.html",
        open_requests=open_reqs,
        my_claimed=my_claimed
    )


@service_requests_bp.route("/provider/requests/<int:request_id>/claim", methods=["POST"])
@login_required
@role_required("provider")
def claim_request(request_id):
    sr = ServiceRequest.query.get_or_404(request_id)

    if sr.status != "open":
        flash("That request is no longer open.", "warning")
        return redirect(url_for("service_requests.provider_requests"))

    sr.status = "claimed"
    sr.claimed_by_provider_id = current_user.id
    sr.updated_at = datetime.utcnow()
    db.session.commit()

    flash("Request claimed.", "success")
    return redirect(url_for("service_requests.provider_requests"))


@service_requests_bp.route("/provider/requests/<int:request_id>/fulfill", methods=["POST"])
@login_required
@role_required("provider")
def fulfill_request(request_id):
    sr = ServiceRequest.query.get_or_404(request_id)

    if sr.status != "claimed" or sr.claimed_by_provider_id != current_user.id:
        abort(403)

    sr.status = "fulfilled"
    sr.updated_at = datetime.utcnow()
    db.session.commit()

    flash("Request marked fulfilled.", "success")
    return redirect(url_for("service_requests.provider_requests"))

#Admin Routes

@service_requests_bp.route("/admin/requests")
@login_required
@role_required("admin")
def admin_requests():
    reqs = ServiceRequest.query.order_by(ServiceRequest.created_at.desc()).all()
    return render_template("admin_requests.html", requests=reqs)


@service_requests_bp.route("/admin/requests/<int:request_id>/close", methods=["POST"])
@login_required
@role_required("admin")
def admin_close_request(request_id):
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