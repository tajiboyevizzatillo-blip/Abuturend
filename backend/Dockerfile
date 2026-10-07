FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Production kutubxonalari (gunicorn, whitenoise, dj-database-url) ham
# requirements.txt ichida — lokal Windows muhitida ham, shu image'da ham
# bitta manba orqali o'rnatiladi.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/media /app/staticfiles \
    && useradd --system --uid 10001 --create-home appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health/', timeout=4).status == 200 else 1)"

# --max-requests recycles workers so a slow memory leak in any single process
# cannot accumulate for the container's lifetime. --worker-class gthread with
# --threads lets a worker overlap I/O-bound aggregation instead of blocking.
# --worker-tmp-dir /dev/shm avoids writing heartbeat files to the overlay fs.
# migrate runs here (single owner) rather than also from CI, so two migrate
# processes never race on the same database.
CMD ["sh", "-c", "python manage.py migrate --noinput && python manage.py collectstatic --noinput --clear && exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --worker-class gthread --workers 3 --threads 2 --timeout 60 --graceful-timeout 30 --backlog 2048 --max-requests 1000 --max-requests-jitter 100 --worker-tmp-dir /dev/shm --access-logfile - --error-logfile - --access-logformat '%({x-forwarded-for}i)s %(h)s %(l)s %(u)s %(t)s \"%(r)s\" %(s)s %(b)s \"%(f)s\" \"%(a)s\"'"]