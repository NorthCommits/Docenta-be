from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import ingestion
from app.core.config import settings
from app.core.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    logger.info("Docenta API starting up in %s mode", settings.environment)
    yield
    # Shutdown
    logger.info("Docenta API shutting down")


app = FastAPI(title="Docenta API", version="0.1.0", lifespan=lifespan)
app.include_router(ingestion.router)

@app.get("/health")
def health() -> dict[str, str]:
    """Liveness check used locally and by Render to confirm the app is up."""
    return {"status": "ok", "environment": settings.environment}