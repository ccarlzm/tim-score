from pathlib import Path
import os

# === Paths ===
# base.py está en: <root>/compcore/compcore/settings/base.py
BASE_DIR = Path(__file__).resolve().parents[3]  # <root>

# === Seguridad / Debug ===
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key-change-me")
DEBUG = os.environ.get("DEBUG", "1") == "1"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "127.0.0.1,localhost").split(",")

# === Apps ===
INSTALLED_APPS = [
    # Django core
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Apps del proyecto
    "compcore.apps.accounts",
    "compcore.apps.events",
    "compcore.apps.judging",
    "compcore.apps.leaderboard",
    "compcore.apps.orgs",
    "compcore.apps.registration",
    "compcore.apps.scoring",
    "compcore.apps.scheduling",  # 👈 NUEVA
]

# === Middleware ===
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# === URLs raíz del proyecto ===
ROOT_URLCONF = "compcore.compcore.urls"

# === Templates ===
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],  # carpeta templates/ a nivel de proyecto
        "APP_DIRS": True,
        "OPTIONS": {
                "context_processors": [
                    "django.template.context_processors.debug",
                    "django.template.context_processors.request",
                    "django.contrib.auth.context_processors.auth",
                    "django.contrib.messages.context_processors.messages",
                ],
        },
    },
]

# === WSGI ===
WSGI_APPLICATION = "compcore.compcore.wsgi.application"

# === Base de datos (SQLite por defecto) ===
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# === Password validators ===
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# === i18n / tz ===
LANGUAGE_CODE = "es"
TIME_ZONE = "America/New_York"
USE_I18N = True
USE_TZ = True

# === Static / Media ===
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# === Auth redirects ===
LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "accounts_profile"
LOGOUT_REDIRECT_URL = "home"

# === Email dev para password reset (opcional) ===
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@example.com")