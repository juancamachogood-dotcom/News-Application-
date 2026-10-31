FROM python:3.14-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DB_ENGINE=sqlite

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        default-libmysqlclient-dev \
        pkg-config \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN python -m pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate --noinput && exec python manage.py runserver 0.0.0.0:8000 --noreload"]
