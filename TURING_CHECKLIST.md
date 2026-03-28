# Turing Deployment Checklist (Service Marketplace)

This checklist assumes you have SSH access to the Turing server and a working Python 3.11 install.

---

## 0) Pre-flight (local)
- Confirm repo is pushed to GitHub (or whatever remote you use)
- Confirm `requirements.txt` exists and includes gunicorn
- Confirm docs exist: `DEPLOYMENT.md`, `DEMO.md`, `PROGRESS.md`

---

## 1) SSH into Turing
ssh <NETID>@turing.cs.olemiss.edu

---

## 2) Choose a deployment directory
Example:

mkdir -p ~/apps
cd ~/apps

---

## 3) Clone the repo
git clone <YOUR_REPO_URL> service_marketplace
cd service_marketplace

If updating an existing clone:

git pull

---

## 4) Create + activate virtual environment
python3.11 -m venv venv
source venv/bin/activate

Verify:

python --version
pip --version

---

## 5) Install dependencies
pip install --upgrade pip
pip install -r requirements.txt

Verify:

python -c "import flask; import gunicorn; print('deps ok')"

---

## 6) Environment variables (PRODUCTION)
Set these *in your shell session* (or in a persistent place like ~/.bashrc if allowed):

export APP_CONFIG=production
export SECRET_KEY='REPLACE_WITH_A_LONG_RANDOM_SECRET'

Optional (if you want a custom DB path/location):
export DATABASE_URL='sqlite:////home/<NETID>/apps/service_marketplace/instance/site.db'

Verify config loads:

APP_CONFIG=production SECRET_KEY='testkey' python -c "from wsgi import app; print(app.config['DEBUG'])"
Expected output: False

---

## 7) One-time database setup
Ensure instance folder exists:

mkdir -p instance

Initialize tables:

flask --app wsgi init-db

Seed roles (idempotent):

flask --app wsgi seed

Create demo accounts (idempotent):

flask --app wsgi create-demo

---

## 8) Run the app with Gunicorn (test)
Start on a non-privileged port (example 8000):

gunicorn -w 2 -b 0.0.0.0:8000 wsgi:app

You should see Gunicorn "Listening at" output.

Stop with Ctrl+C.

---

## 9) Confirm it’s reachable
From your local machine, try:

http://turing.cs.olemiss.edu:8000/

Also test:
- /services
- /auth/login
- /admin/ (after login)

If your course requires a specific port or reverse proxy, adjust accordingly.

---

## 10) Demo-ready commands (anytime)
Reset demo users:

flask --app wsgi delete-demo
flask --app wsgi create-demo

Demo credentials (from DEMO.md):
- admin:    admin_demo@example.com / Password123!
- provider: provider_demo@example.com / Password123!
- client:   client_demo@example.com / Password123!

---

## 11) Common issues
- "SECRET_KEY must be set": you forgot to export SECRET_KEY in production
- "Address already in use": choose a different port, or stop the existing process
- Permission issues writing DB: ensure `instance/` is writable in your deploy directory

---

## 12) (Optional) Keep it running after logout
If allowed, use one of:
- `nohup gunicorn ... &`
- `tmux` / `screen`
(Depends on course/server policy.)
