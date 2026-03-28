from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user

from app.extensions import db
from app.decorators import role_required
from app.models import ProviderProfile, Service

provider_services = Blueprint("provider_services", __name__, url_prefix="/provider/services")


@provider_services.route("/new", methods=["GET", "POST"])
@login_required
@role_required("provider")
def new_service():
    # Must have a provider profile before creating services
    profile = ProviderProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        flash("Create your provider profile before adding services.", "warning")
        return redirect(url_for("provider.profile"))

    if request.method == "GET":
        return render_template("service_new.html")

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
                raise ValueError()
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
    profile = ProviderProfile.query.filter_by(user_id=current_user.id).first()
    if not profile:
        flash("Create your provider profile before viewing services.", "warning")
        return redirect(url_for("provider.profile"))

    services = Service.query.filter_by(provider_profile_id=profile.id).order_by(Service.created_at.desc()).all()
    return render_template("services_my.html", services=services)