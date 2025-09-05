from .base import *
import os
import dj_database_url

# Debug and security
DEBUG = False
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')

# Environment variables
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'fallback-secret-key-for-development')
ALLOWED_HOSTS = os.environ.get('ALLOWED_HOSTS', '').split(',') or ['*', '.railway.app']

# PostgreSQL Database Configuration for Railway
DATABASES = {
    'default': dj_database_url.config(
        default=os.environ.get('DATABASE_URL'),
        conn_max_age=600,
        ssl_require=True,
        engine='django.db.backends.postgresql'
    )
}

# Static files configuration
STATIC_URL = '/static/'
STATIC_ROOT = os.path.join(BASE_DIR, 'staticfiles')
STATICFILES_DIRS = [os.path.join(BASE_DIR, 'static')]

# Whitenoise for static files
MIDDLEWARE.insert(1, 'whitenoise.middleware.WhiteNoiseMiddleware')
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Security settings
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# CORS settings for Railway
CORS_ALLOWED_ORIGINS = [
    "https://*.railway.app",
]
CSRF_TRUSTED_ORIGINS = [
    "https://*.railway.app",
]

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
}

# FALLBACK TO SQLITE IF NO DATABASE_URL (TEMPORARY SOLUTION)
if not os.environ.get('DATABASE_URL'):
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
        }
    }
    print("⚠️  Using SQLite as fallback database - For development only!")
