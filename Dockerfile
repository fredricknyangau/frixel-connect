# ─────────────────────────────────────────────
# Stage 1: builder-install deps into a venv
# ─────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /app

# Create an isolated virtual environment so it's easy to copy to the final stage
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt


# ─────────────────────────────────────────────
# Stage 2: runtime-lean production image
# ─────────────────────────────────────────────
FROM python:3.12-slim AS runtime

RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends postgresql-client && \
    rm -rf /var/lib/apt/lists/*

# Non-root user for security
RUN groupadd --gid 1001 appgroup \
    && useradd --uid 1001 --gid appgroup --no-create-home appuser

WORKDIR /app

# Pull in the pre-built venv from the builder stage (no pip in final image)
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Copy application source (respect .dockerignore to exclude .env, __pycache__, etc.)
COPY --chown=appuser:appgroup . .

USER appuser

EXPOSE 8000

# Default command-overridden per-service in docker-compose.yml
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]