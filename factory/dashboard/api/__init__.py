"""Main FastAPI application for the Software Factory Dashboard."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from prometheus_client import make_asgi_app
import structlog

from factory.config.settings import settings
from factory.dashboard.api.routes import router as api_router
from factory.dashboard.api.metrics import registry as metrics_registry
from factory.orchestration.engine import initialize_engine
from factory.memory.tiered import initialize_tiered_memory
from factory.tools.mcp_client import initialize_mcp_client
from factory.tools.registry import get_tool_registry

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    logger.info("factory_startup")
    
    # Initialize core systems
    try:
        await initialize_tiered_memory()
        logger.info("memory_initialized")
    except Exception as e:
        logger.error("memory_init_failed", error=str(e))
    
    try:
        await initialize_mcp_client()
        logger.info("mcp_initialized")
    except Exception as e:
        logger.error("mcp_init_failed", error=str(e))
    
    try:
        engine = await initialize_engine()
        # Register stage handlers
        from factory.agents import create_agent
        
        engine.register_stage_handler("triage", create_agent("triage").execute)
        engine.register_stage_handler("planning", create_agent("architect").execute)
        engine.register_stage_handler("execution", create_agent("worker_pool").execute)
        engine.register_stage_handler("validation", create_agent("reviewer").execute)
        engine.register_stage_handler("release", create_agent("release").execute)
        engine.register_stage_handler("document", create_agent("documenter").execute)
        engine.register_stage_handler("monitor", create_agent("monitor").execute)
        
        logger.info("engine_initialized")
    except Exception as e:
        logger.error("engine_init_failed", error=str(e))
    
    # Register built-in tools
    get_tool_registry()
    
    yield
    
    # Shutdown
    logger.info("factory_shutdown")


app = FastAPI(
    title="Software Factory API",
    description="Local-first software factory with multi-agent SDLC automation",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount API routes
app.include_router(api_router)

# Mount Prometheus metrics
metrics_app = make_asgi_app(registry=metrics_registry)
app.mount("/metrics", metrics_app)

# Health check
@app.get("/health")
async def health():
    return {"status": "healthy", "service": "software-factory"}


# Root endpoint
@app.get("/")
async def root():
    return {
        "name": "Software Factory",
        "version": "0.1.0",
        "description": "Local-first software factory with multi-agent SDLC automation",
        "docs": "/docs",
        "metrics": "/metrics",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "factory.dashboard.api.routes:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )