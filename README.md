# CompCore – Competition Registration & Scoring (Django skeleton)

This is a beginner-friendly starter you can run locally and then deploy on PythonAnywhere.

## Quickstart (local)

1. **Create a virtual environment** (Windows PowerShell or macOS/Linux Terminal):
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # macOS/Linux
   .venv\Scripts\activate   # Windows
   ```
2. **Install requirements:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Create the database and a superuser:**
   ```bash
   python manage.py migrate
   python manage.py createsuperuser
   ```
4. **Run the dev server:**
   ```bash
   python manage.py runserver
   ```
   Visit http://127.0.0.1:8000 to see the home page. Admin at /admin.

## Deploy on PythonAnywhere (basic)

1. Upload this zip and extract into your PythonAnywhere home folder.
2. Create a **Virtualenv** on PythonAnywhere and install `requirements.txt` there.
3. Create a new **Web app** (Manual config). Point **WSGI file** to: `compcore/compcore/wsgi.py`.
4. Set env var in "Web" > "Environment variables":
   - `DJANGO_SETTINGS_MODULE=compcore.settings.prod`
5. In a Bash console:
   ```bash
   python manage.py migrate
   python manage.py collectstatic --noinput
   ```
6. Reload the web app. Visit your domain.

## What’s included
- Project: `compcore/`
- Apps: accounts, orgs, events, registration, scoring, leaderboard, judging
- Minimal models, admin registrations, URLs, and templates
- DRF-ready `/api/health/`
- Simple leaderboard placeholder
