#!/bin/bash
# Run this script ON THE VULTR SERVER after copying/cloning the file-converter-api project.
# Usage: cd /opt/file-converter-api && bash deploy-vultr.sh

set -e

echo "=========================================="
echo "File Converter API - Vultr Deploy"
echo "=========================================="

if [ ! -f "Dockerfile" ] || [ ! -f "docker-compose.yml" ]; then
    echo "❌ Run this script from the file-converter-api directory (where Dockerfile and docker-compose.yml are)."
    exit 1
fi

echo "Building image..."
docker compose build --no-cache

echo "Starting API..."
docker compose up -d

echo "Waiting for API to be ready..."
sleep 3

if curl -sf http://localhost:5000/api/health > /dev/null; then
    echo "✅ API is running. Health check OK."
    echo "   Local:  http://localhost:5000"
    echo "   Public: http://$(curl -s ifconfig.me 2>/dev/null || echo 'YOUR_SERVER_IP'):5000"
else
    echo "⚠️  API may still be starting. Check: docker compose logs -f api"
fi
