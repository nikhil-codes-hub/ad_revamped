"""
AssistedDiscovery FastAPI Application

Main application entry point for the AssistedDiscovery system.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from app.core.config import settings
from app.core.logging import setup_logging
from app.api.v1.api import api_router

# Setup structured logging
setup_logging()
logger = structlog.get_logger(__name__)

def create_application() -> FastAPI:
    """Create FastAPI application with all configurations."""

    application = FastAPI(
        title="AssistedDiscovery API",
        description="AssistedDiscovery API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json"
    )

    # CORS middleware for Streamlit frontend
    application.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],  # Streamlit default
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API routes
    application.include_router(api_router, prefix="/api/v1")

    # Health check endpoint
    @application.get("/health")
    async def health_check():
        """Simple health check endpoint."""
        return JSONResponse(
            status_code=200,
            content={
                "status": "healthy",
                "version": "1.0.0",
                "service": "AssistedDiscovery API"
            }
        )

    # Global exception handler
    @application.exception_handler(Exception)
    async def global_exception_handler(request, exc):
        logger.error("Unhandled exception",
                    path=request.url.path,
                    method=request.method,
                    error=str(exc))

        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )

    logger.info("FastAPI application created",
                title=application.title,
                version=application.version)

    return application


app = create_application()


if __name__ == "__main__":
    import uvicorn

    logger.info("Starting AssistedDiscovery API server",
                host="127.0.0.1",
                port=8000,
                reload=settings.DEBUG)

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=8000,
        reload=settings.DEBUG,
        log_config=None  # Use our structured logging
    )