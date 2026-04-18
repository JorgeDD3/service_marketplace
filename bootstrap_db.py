# bootstrap_db.py
from sqlalchemy import text

from app import create_app
from app.extensions import db
from app.models import Role


def main() -> None:
    app = create_app()
    with app.app_context():
        # Ensure tables exist
        db.create_all()

        # Ensure core roles exist
        wanted = ["client", "provider", "admin"]
        existing = {r.role_name for r in Role.query.all()}
        created = 0
        for name in wanted:
            if name not in existing:
                db.session.add(Role(role_name=name))
                created += 1
        if created:
            db.session.commit()

        # Print verification
        users_count = db.session.execute(text("SELECT COUNT(*) FROM users")).scalar_one()
        roles_count = db.session.execute(text("SELECT COUNT(*) FROM roles")).scalar_one()
        print(f"[bootstrap_db] users.count={users_count} roles.count={roles_count} roles.created={created}")


if __name__ == "__main__":
    main()