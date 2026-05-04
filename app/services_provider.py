"""
Provider service management blueprint.

This blueprint is the provider-side UI for maintaining marketplace listings:
- create a new service
- view your existing services

I keep provider ownership checks here so the public blueprint can stay focused
on browsing/booking flows.
"""

from __future__ import annotations

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.decorators import role_required
from app.extensions import db
from app.models import ProviderProfile, Service

provider_services = Blueprint("provider_services", __name__, url_prefix="/provider/services")


def _get_provider_profile_or_redirect():
    """Return the current provider profile, or a redirect response if missing.

    Providers must create a profile before they can create/manage services.
    """
    profile = ProviderProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        flash("Create your provider profile before managing services.", "warning")
        return None, redirect(url_for("provider.profile"))
    return profile, None


@provider_services.route("/new", methods=["GET", "POST"])
@login_required
@role_required("provider")
def new_service():
    """Create a new service listing."""
    profile, resp = _get_provider_profile_or_redirect()
    if resp:
        return resp

    if request.method == "GET":
        return render_template("services/service_new.html")

    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip()
    price_raw = (request.form.get("price") or "").strip()

    if not title:
        flash("Title is required.", "danger")
        return redirect(url_for("provider_services.new_service"))

    price = None
    if price_raw:
        try:
            price = float(price_raw)
            if price < 0:
                raise ValueError
        except ValueError:
            flash("Price must be a valid non-negative number.", "danger")
            return redirect(url_for("provider_services.new_service"))

    service = Service(
        provider_profile_id=profile.id,
        title=title,
        description=description or None,
        price=price,
    )
    db.session.add(service)
    db.session.commit()

    flash("Service created.", "success")
    return redirect(url_for("provider_services.my_services"))


@provider_services.route("", methods=["GET"])
@login_required
@role_required("provider")
def my_services():
    """List the current provider's services."""
    profile, resp = _get_provider_profile_or_redirect()
    if resp:
        return resp

    services = (
        Service.query.filter_by(provider_profile_id=profile.id)
        .order_by(Service.created_at.desc())
        .all()
    )
    return render_template("services/services_my.html", services=services)