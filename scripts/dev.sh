#!/bin/bash
# Software Factory - Development Mode

set -e

echo "🏭 Software Factory - Development Mode"
echo "====================================="

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ .env not found. Run ./scripts/setup.sh first."
    exit 1
fi

# Start services with hot reload
echo "Starting development services..."
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

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
echo "  View logs:        docker-compose -f docker-compose.yml -f docker-compose.dev.yml logs -f"
echo "  Restart API:      docker-compose -f docker-compose.yml -f docker-compose.dev.yml restart factory-api"
echo "  Restart Dashboard: docker-compose -f docker-compose.yml -f docker-compose.dev.yml restart factory-dashboard"
echo "  Stop:             docker-compose -f docker-compose.yml -f docker-compose.dev.yml down"
echo ""
echo "To run a factory job:"
echo "  factory run 'Add feature' 'Description' --repo myorg/myapp"
echo ""
echo "To run tests:"
echo "  docker-compose -f docker-compose.yml -f docker-compose.dev.yml exec factory-api pytest tests/ -v"