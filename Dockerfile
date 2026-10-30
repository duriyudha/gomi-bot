FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Tokyo \
    DB_PATH=/data/gomi.db \
    SCHEDULE_PATH=/app/schedule.yml

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY schedule.yml .

# Run as a normal user. /data holds the SQLite file (mounted as a volume).
RUN useradd --create-home --uid 1000 bot && mkdir /data && chown bot:bot /data
USER bot

EXPOSE 8000

HEALTHCHECK --interval=60s --timeout=5s --start-period=10s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')" || exit 1

# Only 1 worker: the reminder scheduler runs inside the app, so 2 workers would send it twice.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
