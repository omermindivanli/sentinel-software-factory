#!/bin/bash
# Sentinel Software Factory - Podman Development Mode

set -e

echo "🛡️ Sentinel Software Factory - Podman Development Mode"
echo "====================================================="

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env not found. Run ./scripts/setup_podman.sh first."
    exit 1
fi

# Start services with hot reload
echo "Starting development services..."
podman-compose -f podman-compose.yml up -d

echo ""
echo "✅ Development services started!"
echo ""
echo "Access points:"
echo "  📊 Dashboard:     http://localhost:5173 (hot reload)"
echo "  🔧 API:           http://localhost:8000 (hot reload)"
echo "  📚 API Docs:      http://localhost:8000/docs"
echo "  📈 Prometheus:    http://localhost:9090"
echo "  📊 Grafana:       http://localhost:3000"
echo ""
echo "Commands:"
echo "  View logs:        podman-compose -f podman-compose.yml logs -f"
echo "  Restart API:      podman-compose -f podman-compose.yml restart factory-api"
echo "  Restart Dashboard: podman-compose -f podman-compose.yml restart factory-dashboard"
echo "  Stop:             podman-compose -f podman-compose.yml down"
echo ""
echo "To run a factory job:"
echo "  factory run 'Add feature' 'Description' --repo myorg/myapp"
echo ""
echo "To run tests:"
echo "  podman-compose -f podman-compose.yml exec factory-api pytest tests/ -v"