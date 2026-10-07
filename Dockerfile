FROM python:3.12-slim

# Chromium нужен только для поиска VK без токена (Google + headless-браузер).
# Если задан VK_ACCESS_TOKEN, можно собрать без него: --build-arg INSTALL_CHROMIUM=false
ARG INSTALL_CHROMIUM=true

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg nodejs ca-certificates \
    && if [ "$INSTALL_CHROMIUM" = "true" ]; then apt-get install -y --no-install-recommends chromium chromium-driver; fi \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini main.py ./
COPY migrations ./migrations
COPY app ./app

RUN useradd --create-home --uid 1000 appuser && mkdir -p /app/var && chown -R appuser /app/var
USER appuser

ENV CHROME_BINARY=/usr/bin/chromium \
    YTDLP_JS_RUNTIMES=node

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=4).status == 200 else 1)"

# Один воркер: очередь рендера живёт в процессе, а сам рендер (ffmpeg) и так использует все ядра.
CMD ["uvicorn", "app.asgi:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1", "--proxy-headers", "--forwarded-allow-ips", "*"]
