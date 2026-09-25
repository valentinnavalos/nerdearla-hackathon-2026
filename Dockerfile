# ---- frontend build stage ----
FROM node:20-slim AS frontend-build
WORKDIR /app/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

# ---- backend runtime stage ----
FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# system-wide install, so the image also runs with --user <host uid> in local dev
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# HF Spaces runs the container as a non-root user with UID 1000
RUN useradd -m -u 1000 user && chmod 755 /home/user
USER user
ENV HOME=/home/user \
    PYTHONUNBUFFERED=1 \
    DATA_DIR=/home/user/app/data
WORKDIR /home/user/app

COPY --chown=user . .
COPY --chown=user --from=frontend-build /app/web/dist ./web/dist

EXPOSE 7860
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "7860", \
     "--ws-ping-interval", "20", "--ws-ping-timeout", "20", \
     "--proxy-headers", "--forwarded-allow-ips", "*"]
