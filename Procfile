web: python manage.py migrate && python manage.py collectstatic --noinput && gunicorn compcore.compcore.wsgi --bind 0.0.0.0:$PORT
