# syntax=docker/dockerfile:1.7

# Stage 1: Build CSS with Node.js
FROM node:20-alpine AS css-builder

WORKDIR /build

COPY package.json package-lock.json* ./
RUN npm ci --silent

COPY tailwind.config.js postcss.config.js ./
COPY src/css ./src/css
COPY templates ./templates

RUN npm run build:css

# Stage 2: Python application
FROM python:3.12-slim-bookworm

WORKDIR /app

ENV DEBIAN_FRONTEND=noninteractive \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_ROOT_USER_ACTION=ignore \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt/lists,sharing=locked \
    rm -f /etc/apt/apt.conf.d/docker-clean \
    && apt-get update -o Acquire::Retries=5 -o Acquire::http::Timeout=30 -o Acquire::https::Timeout=30 \
    && apt-get install -y --no-install-recommends \
        -o Acquire::Retries=5 \
        -o Acquire::http::Timeout=30 \
        -o Acquire::https::Timeout=30 \
        libcairo2 \
        libgdk-pixbuf-2.0-0 \
        libglib2.0-0 \
        libpango-1.0-0 \
        libpangocairo-1.0-0 \
        libffi8 \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --retries 10 --timeout 120 -r requirements.txt

COPY . .

# Copy compiled CSS from builder stage
COPY --from=css-builder /build/static/css/app.css ./static/css/app.css

RUN chmod +x /app/scripts/entrypoint-monitoring.sh

EXPOSE 8001

ENTRYPOINT ["/app/scripts/entrypoint-monitoring.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8001"]
