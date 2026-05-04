"""
Local development entrypoint.

Railway production runs via Procfile/Gunicorn (wsgi:app).
This file is only for running locally with Flask's built-in dev server.
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True)