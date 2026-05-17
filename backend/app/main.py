"""
FastAPI Main Entry Point
Enterprise AI Document Intelligence Platform
"""

from fastapi import FastAPI, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager
import logging
from typing import Dict, Any

from app.config import settings
from app.api.routes import (
    documents, extraction, classification, 
    fraud, dashboard, health
)
from app.database.session import engine, SessionLocal
from app.database.base import Base
from app.utils.logger import setup_logging
from app.utils.exceptions import (
    AppException, 
    app_exception_handler,
    http_exception_handler,
    generic_exception_handler
)

# Setup logging
setup_logging()
logger = logging.getLogger(__name__)

# Create database tables
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan context manager for startup and shutdown events
    """
    # Startup
    logger.info("Starting Enterprise AI Document Intelligence Platform...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug Mode: {settings.DEBUG}")
    
    # Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    logger.info("Database tables created successfully")
    logger.info("Application startup complete")
    
    yield
    
    # Shutdown
    logger.info("Shutting down application...")
    await engine.dispose()
    logger.info("Application shutdown complete")

# Initialize FastAPI app
app = FastAPI(
    title="Enterprise AI Document Intelligence Platform",
    description="""
    ## AI-Powered Document Processing Platform
    
    ### Features:
    - **OCR Processing**: Extract text from images and PDFs using Tesseract and Gemini AI
    - **Document Classification**: Classify documents (Invoices, Contracts, Forms) using BERT
    - **Named Entity Recognition**: Extract key information like names, dates, amounts
    - **Fraud Detection**: Detect anomalies, fake documents, and suspicious patterns
    - **Auto-fill ERP Systems**: Seamless integration with ERP systems
    
    ### Technologies:
    - FastAPI for high-performance APIs
    - BERT for NLP tasks
    - Tesseract + Gemini for OCR
    - PostgreSQL for data persistence
    - Redis for caching
    - Celery for async tasks
    """,
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add Trusted Host middleware
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS,
)

# Register exception handlers
app.add_exception_handler(AppException, app_exception_handler)
app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(Exception, generic_exception_handler)

# Include routers
app.include_router(health.router, prefix="/api/v1", tags=["Health"])
app.include_router(documents.router, prefix="/api/v1/documents", tags=["Documents"])
app.include_router(extraction.router, prefix="/api/v1/extraction", tags=["Extraction"])
app.include_router(classification.router, prefix="/api/v1/classification", tags=["Classification"])
app.include_router(fraud.router, prefix="/api/v1/fraud", tags=["Fraud Detection"])
app.include_router(dashboard.router, prefix="/api/v1/dashboard", tags=["Dashboard"])

# Root endpoint
@app.get("/")
async def root() -> Dict[str, Any]:
    """
    Root endpoint with API information
    """
    return {
        "name": "Enterprise AI Document Intelligence Platform",
        "version": "1.0.0",
        "status": "running",
        "docs": "/api/docs",
        "redoc": "/api/redoc",
        "health": "/api/v1/health",
        "endpoints": {
            "documents": "/api/v1/documents",
            "extraction": "/api/v1/extraction",
            "classification": "/api/v1/classification",
            "fraud": "/api/v1/fraud",
            "dashboard": "/api/v1/dashboard"
        }
    }

# Health check endpoint
@app.get("/health")
async def health_check() -> Dict[str, str]:
    """
    Simple health check endpoint
    """
    return {"status": "healthy", "service": "document-intelligence-api"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL
    )