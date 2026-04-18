"""
check_setup.py

Run:
  python check_setup.py

What it checks:
- App factory can create the app
- Flask extensions are initialized (db, login_manager)
- Blueprints registered (auth)
- Templates folder is discoverable
- Database tables exist
- Roles exist (client/provider/admin)
- User model has expected fields
- login_manager.user_loader is present

Also prints key production/proxy-related config values (cookies, scheme, etc.).
"""

import os
import sys
import traceback


def banner(msg: str):
    print("\n" + "=" * 70)
    print(msg)
    print("=" * 70)


def ok(msg: str):
    print(f"[OK]  {msg}")


def warn(msg: str):
    print(f"[WARN]{msg}")


def fail(msg: str):
    print(f"[FAIL]{msg}")


def print_cookie_and_proxy_config(app):
    banner("Config — Proxy/Cookies (sanity)")

    ok(f"ENV APP_CONFIG: {os.getenv('APP_CONFIG')}")
    ok(f"PREFERRED_URL_SCHEME: {app.config.get('PREFERRED_URL_SCHEME')}")
    ok(f"SESSION_COOKIE_PATH: {app.config.get('SESSION_COOKIE_PATH')}")
    ok(f"SESSION_COOKIE_SECURE: {app.config.get('SESSION_COOKIE_SECURE')}")
    ok(f"SESSION_COOKIE_HTTPONLY: {app.config.get('SESSION_COOKIE_HTTPONLY')}")
    ok(f"SESSION_COOKIE_SAMESITE: {app.config.get('SESSION_COOKIE_SAMESITE')}")
    ok(f"REMEMBER_COOKIE_SECURE: {app.config.get('REMEMBER_COOKIE_SECURE')}")
    ok(f"REMEMBER_COOKIE_HTTPONLY: {app.config.get('REMEMBER_COOKIE_HTTPONLY')}")
    ok(f"REMEMBER_COOKIE_SAMESITE: {app.config.get('REMEMBER_COOKIE_SAMESITE')}")


def main():
    banner("Service Marketplace — Setup Check")

    # ---- Step A: Import create_app ----
    try:
        from app import create_app
        ok("Imported create_app() from app")
    except Exception:
        fail("Could not import create_app() from app. Check app/__init__.py exports create_app.")
        traceback.print_exc()
        sys.exit(1)

    # ---- Step B: Create app ----
    try:
        app = create_app()
        ok("create_app() executed successfully")
    except Exception:
        fail("create_app() failed. See traceback.")
        traceback.print_exc()
        sys.exit(1)

    # ---- Step C: Inspect config ----
    try:
        ok(f"App name: {app.name}")
        ok(f"ENV FLASK_ENV: {os.getenv('FLASK_ENV')}")
        ok(f"SECRET_KEY set: {'YES' if app.config.get('SECRET_KEY') else 'NO'}")
        ok(f"SQLALCHEMY_DATABASE_URI: {app.config.get('SQLALCHEMY_DATABASE_URI')}")
    except Exception:
        warn("Could not print some config values (non-fatal).")

    # ---- Step C2: Print cookie/proxy config (helps with Turing reverse proxy debugging) ----
    try:
        print_cookie_and_proxy_config(app)
    except Exception:
        warn("Could not print cookie/proxy config values (non-fatal).")
        traceback.print_exc()

    # ---- Step D: Check extensions ----
    try:
        from app.extensions import db, login_manager
        ok("Imported db and login_manager from app.extensions")
    except Exception:
        fail("Could not import db/login_manager from app.extensions")
        traceback.print_exc()
        sys.exit(1)

    with app.app_context():
        # ---- Step E: Check blueprint registrations ----
        try:
            bps = list(app.blueprints.keys())
            ok(f"Registered blueprints: {bps}")
            if "auth" not in bps:
                warn("Blueprint 'auth' not found. If you haven't created it yet, that's fine.")
        except Exception:
            warn("Could not list blueprints (non-fatal).")

        # ---- Step F: Check templates folder ----
        try:
            j = app.jinja_loader
            ok(f"Jinja loader: {type(j).__name__}")
        except Exception:
            warn("Template loader check failed (non-fatal).")

        # ---- Step G: Check DB connectivity and tables ----
        try:
            _ = db.engine
            ok("DB engine reachable")
        except Exception:
            fail("DB engine not reachable. db.init_app(app) may not be running in create_app().")
            traceback.print_exc()
            sys.exit(1)

        try:
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            ok(f"Tables found: {tables}")

            expected = {
                "users",
                "roles",
                "provider_profiles",
                "services",
                "bookings",
                "service_requests",
            }
            missing = sorted(list(expected - set(tables)))
            if missing:
                warn(f"Missing expected tables: {missing} (Did you run db.create_all()?)")
            else:
                ok("All expected tables exist")
        except Exception:
            fail("Table inspection failed.")
            traceback.print_exc()
            sys.exit(1)

        # ---- Step H: Check models and role rows ----
        try:
            from app.models import Role, User
            ok("Imported Role and User models")
        except Exception:
            fail("Could not import Role/User from app.models")
            traceback.print_exc()
            sys.exit(1)

        # Check Role rows (supports either 'name' or 'role_name' column naming)
        try:
            if hasattr(Role, "role_name"):
                role_col = Role.role_name
                role_attr = "role_name"
            elif hasattr(Role, "name"):
                role_col = Role.name
                role_attr = "name"
            else:
                raise AttributeError("Role model has neither 'role_name' nor 'name' attribute.")

            role_rows = Role.query.order_by(role_col.asc()).all()
            role_names = [getattr(r, role_attr) for r in role_rows]

            ok(f"Role rows in DB: {role_names}")

            needed = {"client", "provider", "admin"}
            if not needed.issubset(set(role_names)):
                warn("Not all roles are present. You should run `flask seed` after adding cli.py.")
            else:
                ok("All required roles present")
        except Exception:
            warn("Could not query Role table (non-fatal).")
            traceback.print_exc()

        # Check User fields
        try:
            u = User()
            for field in ["email", "password_hash", "role_id"]:
                if not hasattr(u, field):
                    warn(f"User model missing expected field: {field}")
                else:
                    ok(f"User has field: {field}")

            if hasattr(User, "role"):
                ok("User has relationship: role")
            else:
                warn("User missing relationship: role (recommended for RBAC).")
        except Exception:
            warn("User model field check failed (non-fatal).")
            traceback.print_exc()

        # ---- Step I: Check Flask-Login user_loader ----
        try:
            loader = login_manager._user_callback
            if loader is None:
                warn("login_manager.user_loader is NOT configured (loader callback missing).")
            else:
                ok("login_manager.user_loader callback is configured")
        except Exception:
            warn("Could not inspect login_manager user_loader callback (non-fatal).")
            traceback.print_exc()

    banner("Done. If you see WARN/FAIL, paste the output here and we'll fix in order.")


if __name__ == "__main__":
    main()