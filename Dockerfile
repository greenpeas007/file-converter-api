# File Converter API - production image
FROM python:3.11-slim

WORKDIR /app

# Install runtime deps for Pillow (optional, for some image formats) and PyMuPDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    libjpeg-dev zlib1g-dev libwebp-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .

# Gunicorn: bind to 0.0.0.0:5000, 2 workers, 120s timeout for large uploads
ENV PORT=5000
EXPOSE 5000
CMD ["sh", "-c", "gunicorn --bind 0.0.0.0:${PORT} --workers 2 --timeout 120 --access-logfile - --error-logfile - app:app"]
