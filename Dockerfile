# Software Factory - Dockerfile

FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    docker.io \
    ripgrep \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
WORKDIR /app
COPY pyproject.toml README.md ./
RUN pip install --no-cache-dir -e ".[dev]"

# Install frontend dependencies
COPY dashboard-frontend/package.json dashboard-frontend/package-lock.json* ./dashboard-frontend/
RUN cd dashboard-frontend && (npm ci 2>/dev/null || npm install)

# Copy source code
COPY factory/ ./factory/
COPY dashboard-frontend/ ./dashboard-frontend/

# Build frontend
RUN cd dashboard-frontend && npm run build

# Create non-root user
RUN useradd -m -u 1000 factory && \
    chown -R factory:factory /app

USER factory

# Expose ports
EXPOSE 8000 5173

# Default command
CMD ["uvicorn", "factory.dashboard.api.routes:app", "--host", "0.0.0.0", "--port", "8000"]