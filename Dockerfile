# ==============================================================================
# Webook Auto-Booker Bot - Dockerfile for Render.com
# Base Image: Official Microsoft Playwright Python with all browser dependencies
# ==============================================================================
FROM mcr.microsoft.com/playwright/python:v1.44.0-jammy

# Set working directory
WORKDIR /app

# Set production environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=10000 \
    DEBIAN_FRONTEND=noninteractive

# Copy requirements file first to take advantage of Docker layer caching
COPY requirements.txt .

# Install Python packages
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Ensure Chromium browser binary is installed and verified
RUN playwright install chromium

# Copy application source code
COPY . .

# Expose default Render port
EXPOSE 10000

# Health check to ensure Flask server is responsive
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:${PORT:-10000}/api/status || exit 1

# Start Gunicorn server binding to dynamic Render $PORT with 1 worker to conserve RAM
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT:-10000} --workers 1 --threads 2 --worker-class sync --timeout 300 --access-logfile - --error-logfile - app:app"]
