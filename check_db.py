# check_db.py
from sqlalchemy import text
from app import create_app
from app.extensions import db


def main() -> None:
    app = create_app()
    with app.app_context():
        # Print which DB we're on
        uri = app.config.get("SQLALCHEMY_DATABASE_URI")
        print(f"[check_db] SQLALCHEMY_DATABASE_URI={uri}")

        # Count users
        users_count = db.session.execute(text("SELECT COUNT(*) FROM users")).scalar_one()
        print(f"[check_db] users.count={users_count}")

        # Inspect users.password_hash column in Postgres (information_schema)
        # Works on Postgres; on SQLite this will fail, so we guard it.
        try:
            row = db.session.execute(
                text(
                    """
                    SELECT data_type, character_maximum_length
                    FROM information_schema.columns
                    WHERE table_name='users' AND column_name='password_hash'
                    """
                )
            ).first()
            print(f"[check_db] users.password_hash={row}")
        except Exception as e:
            print(f"[check_db] info_schema_check_skipped ({type(e).__name__}): {e}")


if __name__ == "__main__":
    main()