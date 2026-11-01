# syntax=docker/dockerfile:1
# Multi-Arch-Build: linux/amd64 + linux/arm64 (Raspberry Pi)

# --- 1) Frontend bauen (SvelteKit -> statisch) ---
# Auf der Build-Plattform: Das Ergebnis sind plattformunabhängige statische
# Dateien. Unter QEMU (arm64-Emulation) crashte Vite regelmäßig mit
# "qemu: uncaught target signal 4 (Illegal instruction)".
FROM --platform=$BUILDPLATFORM node:24-alpine AS frontend
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./frontend/
RUN cd frontend && npm ci --no-audit --no-fund
COPY frontend/ ./frontend/
RUN cd frontend && npm run build

# --- 2) Python-Abhängigkeiten mit uv einrichten ---
FROM python:3.13-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=never
WORKDIR /app/backend
# Zuerst nur Manifeste kopieren -> Dependency-Layer wird gecacht
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ ./

# --- 3) Runtime ---
FROM python:3.13-slim AS runtime
# Git-SHA des Builds (vom CI gesetzt) – vom Update-Checker zum Abgleich
# mit dem neuesten GHCR-Image verwendet.
ARG GIT_SHA=unknown
ENV GIT_SHA=$GIT_SHA
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/backend/.venv/bin:$PATH" \
    ENVIRONMENT=production \
    DATA_DIR=/app/data \
    FRONTEND_DIR=/app/frontend \
    EMBED_PUBLIC=true \
    CORS_ORIGINS="*" \
    AUTO_MIGRATE=true \
    TZ=Europe/Berlin

RUN apt-get update \
    && apt-get install -y --no-install-recommends tzdata \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app/backend
COPY --from=builder /app/backend/.venv /app/backend/.venv
COPY backend/ ./
COPY --from=frontend /src/frontend/build /app/frontend

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8080/api/v1/health', timeout=4).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
