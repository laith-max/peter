# Image for Peter — Jetson device-side logging and privacy filter.
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY robot/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Health check: the privacy self-test is the supervisor's gating check,
# so we reuse it here. A non-zero exit means the filter is misconfigured
# and the container should be considered unhealthy.
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -m jetson_logging || exit 1

# Default command
CMD ["python", "-m", "jetson_logging"]
