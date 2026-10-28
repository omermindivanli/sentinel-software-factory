#!/bin/bash
# Software Factory - Development Setup Script

set -e

echo "🏭 Software Factory - Development Setup"
echo "======================================"

# Check prerequisites
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo "❌ $1 not found. Please install $1 first."
        exit 1
    fi
    echo "✓ $1 found"
}

echo "Checking prerequisites..."
check_command docker
check_command docker-compose
check_command python3
check_command node
check_command npm

# Create .env if not exists
if [ ! -f .env ]; then
    echo "Creating .env from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your API keys"
else
    echo "✓ .env exists"
fi

# Create data directories
echo "Creating data directories..."
mkdir -p .factory/data .factory/work .factory/logs .factory/checkpoints

# Build and start services
echo "Building Docker images..."
docker-compose -f docker-compose.yml -f docker-compose.dev.yml build

echo "Starting services..."
docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# Wait for services to be healthy
echo "Waiting for services to be ready..."
sleep 10

# Check health
echo "Checking service health..."
for service in factory-api factory-dashboard redis chroma neo4j ollama; do
    if docker-compose -f docker-compose.yml -f docker-compose.dev.yml ps $service | grep -q "Up"; then
        echo "✓ $service is running"
    else
        echo "⚠️  $service may not be ready yet"
    fi
done

# Initialize database schemas
echo "Initializing database schemas..."
docker-compose -f docker-compose.yml -f docker-compose.dev.yml exec -T factory-api python -c "
from factory.memory.vector_store import initialize_vector_store
from factory.memory.graph_store import initialize_graph_store
from factory.memory.kv_store import initialize_kv_store
import asyncio
asyncio.run(initialize_vector_store())
asyncio.run(initialize_graph_store())
asyncio.run(initialize_kv_store())
print('Database schemas initialized')
"

echo ""
echo "✅ Setup complete!"
echo ""
echo "Access points:"
echo "  📊 Dashboard:     http://localhost:5173"
echo "  🔧 API:           http://localhost:8000"
echo "  📚 API Docs:      http://localhost:8000/docs"
echo "  📈 Prometheus:    http://localhost:9090"
echo "  📊 Grafana:       http://localhost:3000 (admin/factory123)"
echo ""
echo "Next steps:"
echo "  1. Edit .env with your API keys (ANTHROPIC_API_KEY required)"
echo "  2. Restart services: docker-compose -f docker-compose.yml -f docker-compose.dev.yml restart"
echo "  3. Create your first run via the Dashboard or CLI:"
echo "     factory run 'Add feature' 'Description' --repo myorg/myapp"
echo ""
echo "To view logs: docker-compose -f docker-compose.yml -f docker-compose.dev.yml logs -f"
echo "To stop:      docker-compose -f docker-compose.yml -f docker-compose.dev.yml down"