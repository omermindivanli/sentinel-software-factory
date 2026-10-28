#!/bin/bash
# Software Factory - Production Deploy Script

set -e

VERSION=${1:-latest}
REGISTRY=${2:-your-registry.com}

echo "🏭 Software Factory - Production Deploy"
echo "======================================"
echo "Version: $VERSION"
echo "Registry: $REGISTRY"

# Build production images
echo "Building production images..."
docker-compose -f docker-compose.yml build

# Tag images
echo "Tagging images..."
docker tag software-factory_factory-api:latest $REGISTRY/software-factory/api:$VERSION
docker tag software-factory_factory-dashboard:latest $REGISTRY/software-factory/dashboard:$VERSION

# Push to registry
echo "Pushing to registry..."
docker push $REGISTRY/software-factory/api:$VERSION
docker push $REGISTRY/software-factory/dashboard:$VERSION

# Deploy (example for Kubernetes)
if command -v kubectl &> /dev/null; then
    echo "Deploying to Kubernetes..."
    kubectl set image deployment/factory-api api=$REGISTRY/software-factory/api:$VERSION
    kubectl set image deployment/factory-dashboard dashboard=$REGISTRY/software-factory/dashboard:$VERSION
    kubectl rollout status deployment/factory-api
    kubectl rollout status deployment/factory-dashboard
else
    echo "⚠️  kubectl not found. Skipping Kubernetes deployment."
    echo "Images pushed to registry. Deploy manually or use your CI/CD pipeline."
fi

echo ""
echo "✅ Deploy complete!"
echo "Images: $REGISTRY/software-factory/api:$VERSION, $REGISTRY/software-factory/dashboard:$VERSION"