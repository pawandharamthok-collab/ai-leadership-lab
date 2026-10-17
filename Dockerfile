# ==============================================================================
# AI Leadership Lab - Production Multi-Stage Container
# Always-Free Cloud Run Ready | Zero-Trust Hardened | Non-Root Execution
# ==============================================================================

FROM python:3.12-slim

# Prevent Python from writing .pyc files and enable unbuffered logging
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    APP_ENV=production

# Set standard working directory
WORKDIR /app

# Install minimal OS dependencies for network & cryptography operations
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency definition and install packages
COPY requirements.txt .

# Install dependencies (filtering out Windows-specific pywin32) and install gunicorn
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir gunicorn

# Copy application source code
COPY . /app

# Ensure non-root security: create unprivileged system user
RUN useradd -m -u 1001 appuser && \
    chown -R appuser:appuser /app

# Switch to unprivileged user
USER appuser

# Expose standard Cloud Run HTTP port
EXPOSE 8080

# Production startup using Gunicorn WSGI server (scales cleanly, handles timeouts)
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-8080} --workers 1 --threads 4 --timeout 120 server:app"]
