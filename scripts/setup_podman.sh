#!/bin/bash
# Sentinel Software Factory - Podman Setup Script

set -e

echo "🛡️ Sentinel Software Factory - Podman Setup"
echo "============================================"

# Check prerequisites
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo "❌ $1 not found. Please install $1 first."
        exit 1
    fi
    echo "✓ $1 found ($( $1 --version 2>/dev/null | head -1 ))"
}

echo "Checking prerequisites..."
check_command podman
check_command podman-compose
check_command python3
check_command node
check_command npm
check_command git

# Check Podman machine (for macOS)
if [[ "$OSTYPE" == "darwin"* ]]; then
    echo "Checking Podman machine..."
    if ! podman machine list | grep -q "Currently running"; then
        echo "Starting Podman machine..."
        podman machine start
        sleep 3
    fi
    echo "✓ Podman machine running"
fi

# Create .env if not exists
if [ ! -f .env ]; then
    echo "Creating .env from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env with your API keys (especially ANTHROPIC_API_KEY)"
fi

# Create data directories
echo "Creating data directories..."
mkdir -p .factory/data .factory/work .factory/logs .factory/checkpoints

# Create Podman network if not exists
echo "Creating Podman network..."
podman network exists factory-network 2>/dev/null || podman network create factory-network

# Build images
echo "Building Podman images..."
podman-compose -f podman-compose.yml build

# Start services
echo "Starting services..."
podman-compose -f podman-compose.yml up -d

# Wait for services to be healthy
echo "Waiting for services to be ready..."
sleep 10

# Check health
echo "Checking service health..."
for service in factory-api factory-dashboard redis chroma neo4j ollama prometheus grafana; do
    if podman-compose -f podman-compose.yml ps $service | grep -q "Up"; then
        echo "✓ $service is running"
    else
        echo "⚠️  $service may not be ready yet"
    fi
done

# Initialize database schemas
echo "Initializing database schemas..."
podman-compose -f podman-compose.yml exec -T factory-api python -c "
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
echo "  🔍 Neo4j:         http://localhost:7474"
echo "  🧠 ChromaDB:      http://localhost:8001"
echo ""
echo "Next steps:"
echo "  1. Edit .env with your ANTHROPIC_API_KEY (required)"
echo "  2. Restart: podman-compose -f podman-compose.yml restart"
echo "  3. Create your first run:"
echo "     factory run 'Add user authentication' 'Implement JWT with refresh tokens' --repo myorg/myapp"
echo ""
echo "To view logs: podman-compose -f podman-compose.yml logs -f"
echo "To stop:      podman-compose -f podman-compose.yml down"