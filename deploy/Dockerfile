# Build only after approved registry/build costs. No secrets in image/build args.
FROM python:3.12-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg ca-certificates && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY recorder/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY recorder /app/recorder
RUN useradd --uid 10001 --create-home archive
USER 10001
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 ARCHIVE_ENABLED=false
ENTRYPOINT ["python", "-m", "recorder.worker"]
