from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status

from app.config import settings
from app.storage import init_db, check_db_health
from app.logging_utils import setup_logging, RequestLoggingMiddleware


# Setup structured JSON logging
setup_logging(settings.LOG_LEVEL)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events.
    - Startup: Initialize database and create tables
    - Shutdown: Cleanup resources
    """
    # Startup
    init_db()
    yield
    # Shutdown (cleanup if needed)


app = FastAPI(
    title="Webhook API",
    description="Production-style FastAPI service for WhatsApp-like messages",
    version="1.0.0",
    lifespan=lifespan,
)

# Add request logging middleware
app.add_middleware(RequestLoggingMiddleware)


# =============================================================================
# Health Check Routes
# =============================================================================

@app.get("/health/live")
async def health_live():
    """
    Liveness probe - always returns 200 once the app is running.
    Used by orchestrators to determine if the app needs to be restarted.
    """
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready(response: Response):
    """
    Readiness probe - returns 200 only if:
    1. DB is reachable and schema is applied
    2. WEBHOOK_SECRET is set (non-empty)
    
    Otherwise returns 503 (Service Unavailable).
    """
    # Check if WEBHOOK_SECRET is set
    if not settings.WEBHOOK_SECRET:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "not_ready",
            "reason": "WEBHOOK_SECRET not configured"
        }
    
    # Check if DB is reachable and schema is applied 
    if not check_db_health():
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "not_ready",
            "reason": "Database not reachable or schema not applied"
        }
    
    return {"status": "ready"}
