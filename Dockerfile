FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Paquetes del sistema (libpq para PostgreSQL)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Dependencias Python
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Código de la app
COPY . .

# Ajusta el settings de producción
ENV DJANGO_SETTINGS_MODULE=compcore.compcore.settings.prod
ENV PORT=8000

# Arranque: migra, colecta estáticos y levanta Gunicorn
CMD python manage.py migrate && \
    python manage.py collectstatic --noinput && \
    gunicorn compcore.compcore.wsgi:application --bind 0.0.0.0:$PORT
