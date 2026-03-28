# app/cli.py
from flask import current_app
from werkzeug.security import generate_password_hash

from .extensions import db
from .models import Role, User, ProviderProfile, Service


def register_cli_commands(app):
    @app.cli.command("init-db")
    def init_db():
        """Create database tables."""
        with current_app.app_context():
            db.create_all()
        print("✅ Database tables created (db.create_all).")

    @app.cli.command("seed")
    def seed():
        """Seed initial data like roles."""
        roles = ["client", "provider", "admin"]
        created = 0

        for role_name in roles:
            exists = Role.query.filter_by(role_name=role_name).first()
            if not exists:
                db.session.add(Role(role_name=role_name))
                created += 1

        db.session.commit()
        print(f"Seed complete. Roles created: {created}")

    @app.cli.command("create-demo")
    def create_demo():
        """Create demo accounts and demo marketplace data. Idempotent."""
        roles = {r.role_name: r for r in Role.query.all()}
        missing = [x for x in ["admin", "provider", "client"] if x not in roles]
        if missing:
            print(f"Missing roles: {missing}. Run `flask --app wsgi seed` first.")
            return

        def get_or_create_user(first, last, email, password, role_name):
            user = User.query.filter_by(email=email).first()
            if user:
                return user, False
            user = User(
                first_name=first,
                last_name=last,
                email=email,
                password_hash=generate_password_hash(password),
                role_id=roles[role_name].id,
                is_active=True,
            )
            db.session.add(user)
            db.session.commit()
            return user, True

        created_any = False

        admin, c1 = get_or_create_user(
            "Demo", "Admin", "admin_demo@example.com", "Password123!", "admin"
        )
        provider, c2 = get_or_create_user(
            "Demo", "Provider", "provider_demo@example.com", "Password123!", "provider"
        )
        client, c3 = get_or_create_user(
            "Demo", "Client", "client_demo@example.com", "Password123!", "client"
        )
        created_any = c1 or c2 or c3

        # Ensure provider profile exists for provider demo
        prof = ProviderProfile.query.filter_by(user_id=provider.id).first()
        if not prof:
            prof = ProviderProfile(user_id=provider.id)

            optional_defaults = {
                "business_name": "Demo Provider",
                "company_name": "Demo Provider",
                "display_name": "Demo Provider",
                "name": "Demo Provider",
                "bio": "Demo provider account offering sample services for capstone demos.",
                "about": "Demo provider account offering sample services for capstone demos.",
                "description": "Demo provider account offering sample services for capstone demos.",
            }
            for field, value in optional_defaults.items():
                if hasattr(ProviderProfile, field):
                    setattr(prof, field, value)

            db.session.add(prof)
            db.session.commit()
            created_any = True

        # Ensure provider verification row exists (idempotent)
        prof.get_or_create_verification()

        # Demo services for provider demo
        sample_services = [
            {
                "title": "Golf Lessons",
                "description": (
                    "Improve your swing, consistency, and confidence with personalized 1-on-1 coaching. "
                    "Lessons are tailored to your goals—whether you're brand new to the game or trying to lower your handicap. "
                    "We’ll work on fundamentals, alignment, short game, and course strategy."
                ),
                "price": 60.00,
                "category": "Sports & Fitness",
            },
            {
                "title": "Accounting Tutoring",
                "description": (
                    "Get help with accounting fundamentals, homework, exam prep, and problem-solving strategies. "
                    "Ideal for students in introductory and intermediate accounting courses who want structured support."
                ),
                "price": 45.00,
                "category": "Academic Support",
            },
            {
                "title": "Computer Science Tutoring",
                "description": (
                    "One-on-one help with Python, problem solving, debugging, and core computer science concepts. "
                    "Great for students who want guided practice and clearer understanding outside class."
                ),
                "price": 50.00,
                "category": "Tech Help",
            },
            {
                "title": "Study Skills Coaching",
                "description": (
                    "Build stronger habits for time management, exam preparation, note-taking, and staying organized. "
                    "A practical option for students who want to improve performance across multiple classes."
                ),
                "price": 35.00,
                "category": "Academic Support",
            },
        ]

        services_created = 0

        for item in sample_services:
            existing = Service.query.filter_by(
                provider_profile_id=prof.id,
                title=item["title"],
            ).first()

            if existing:
                if hasattr(existing, "category") and not getattr(existing, "category", None):
                    existing.category = item["category"]
                    db.session.commit()
                continue

            service = Service(
                provider_profile_id=prof.id,
                title=item["title"],
                description=item["description"],
                price=item["price"],
                is_active=True,
            )

            if hasattr(Service, "category"):
                service.category = item["category"]

            db.session.add(service)
            services_created += 1

        if services_created:
            db.session.commit()
            created_any = True

        print("Demo accounts ready:")
        print("  admin:    admin_demo@example.com / Password123!")
        print("  provider: provider_demo@example.com / Password123!")
        print("  client:   client_demo@example.com / Password123!")
        print(f"  demo services created: {services_created}")
        if not created_any:
            print("(No changes; demo data already existed.)")

    @app.cli.command("delete-demo")
    def delete_demo():
        """Delete demo accounts (admin/provider/client) and related provider profile. Idempotent."""
        emails = [
            "admin_demo@example.com",
            "provider_demo@example.com",
            "client_demo@example.com",
        ]

        users = User.query.filter(User.email.in_(emails)).all()
        if not users:
            print("No demo users found. Nothing to delete.")
            return

        # Delete provider profile first (if any)
        provider = next((u for u in users if u.email == "provider_demo@example.com"), None)
        if provider:
            prof = ProviderProfile.query.filter_by(user_id=provider.id).first()
            if prof:
                db.session.delete(prof)

        # NOTE: If you have FK constraints to bookings/services/etc, this may fail.
        # If it fails, we’ll adjust to delete dependent rows safely.
        for u in users:
            db.session.delete(u)

        db.session.commit()
        print("✅ Demo accounts deleted.")