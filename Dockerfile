# syntax=docker/dockerfile:1.7
# ── AgentFactory Orchestrator — Cloud Run deployment ──────────────────────────
# Multi-stage build: keeps the final image lean (~200MB vs ~800MB).

# ── Stage 1: dependency builder ───────────────────────────────────────────────
FROM python:3.12-slim AS builder

# System deps needed only for building (not runtime)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user for build stage
RUN useradd --create-home --shell /bin/bash appuser

WORKDIR /app

# Copy dependency spec first for layer caching
COPY pyproject.toml ./
COPY README.md ./

# Install into a prefix we'll copy to the final stage
RUN pip install --no-cache-dir --prefix=/install .


# ── Stage 2: runtime ──────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# Security: run as non-root
RUN useradd --create-home --uid 1000 --shell /bin/bash appuser

# Copy installed packages from builder
COPY --from=builder /install /usr/local

WORKDIR /app

# Copy application code
COPY apps/ ./apps/

# Cloud Run sets PORT env var; default to 8080
ENV PORT=8080 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Health check — Cloud Run uses this to determine readiness
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

USER appuser

EXPOSE 8080

# Use exec form so signals are passed directly to uvicorn (clean shutdown)
CMD ["sh", "-c", "uvicorn apps.orchestrator.main:app --host 0.0.0.0 --port ${PORT} --workers 1 --log-level info"]
