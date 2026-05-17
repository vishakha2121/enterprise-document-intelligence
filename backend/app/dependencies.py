"""
FastAPI Dependencies
Used for dependency injection across the application
"""

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from functools import lru_cache
import redis
import logging

from app.config import settings
from app.database.session import get_db
from app.utils.cache import RedisCache
from app.services.document_service import DocumentService
from app.services.extraction_service import ExtractionService
from app.services.classification_service import ClassificationService
from app.services.fraud_service import FraudService
from app.services.cache_service import CacheService
from app.core.ocr.ocr_factory import OCRFactory
from app.core.nlp.model_loader import ModelLoader

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer(auto_error=False)

# Global instances (singletons)
_ocr_factory = None
_model_loader = None
_redis_client = None
_cache_service = None

# Database dependency
async def get_db_session() -> AsyncSession:
    """
    Get database session dependency
    """
    async for session in get_db():
        yield session

# Redis cache dependency
def get_redis_client() -> redis.Redis:
    """
    Get Redis client dependency (singleton)
    """
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            # Test connection
            _redis_client.ping()
            logger.info("Redis connection established")
        except Exception as e:
            logger.warning(f"Redis connection failed: {e}. Running without cache.")
            _redis_client = None
    return _redis_client

# Cache service dependency
def get_cache_service() -> Optional[CacheService]:
    """
    Get cache service dependency
    """
    global _cache_service
    if _cache_service is None and settings.ENABLE_REDIS_CACHE:
        redis_client = get_redis_client()
        if redis_client:
            _cache_service = CacheService(redis_client)
    return _cache_service

# OCR Factory dependency
def get_ocr_factory() -> OCRFactory:
    """
    Get OCR factory dependency (singleton)
    """
    global _ocr_factory
    if _ocr_factory is None:
        _ocr_factory = OCRFactory()
    return _ocr_factory

# Model Loader dependency
def get_model_loader() -> ModelLoader:
    """
    Get model loader dependency (singleton)
    """
    global _model_loader
    if _model_loader is None:
        _model_loader = ModelLoader()
    return _model_loader

# Service dependencies
async def get_document_service(
    db: AsyncSession = Depends(get_db_session),
    cache_service: Optional[CacheService] = Depends(get_cache_service)
) -> DocumentService:
    """
    Get document service instance
    """
    return DocumentService(db, cache_service)

async def get_extraction_service(
    db: AsyncSession = Depends(get_db_session),
    ocr_factory: OCRFactory = Depends(get_ocr_factory),
    cache_service: Optional[CacheService] = Depends(get_cache_service)
) -> ExtractionService:
    """
    Get extraction service instance
    """
    return ExtractionService(db, ocr_factory, cache_service)

async def get_classification_service(
    model_loader: ModelLoader = Depends(get_model_loader),
    cache_service: Optional[CacheService] = Depends(get_cache_service)
) -> ClassificationService:
    """
    Get classification service instance
    """
    return ClassificationService(model_loader, cache_service)

async def get_fraud_service(
    db: AsyncSession = Depends(get_db_session),
    cache_service: Optional[CacheService] = Depends(get_cache_service)
) -> FraudService:
    """
    Get fraud detection service instance
    """
    return FraudService(db, cache_service)

# Authentication dependency
async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
    db: AsyncSession = Depends(get_db_session)
) -> Optional[Dict[str, Any]]:
    """
    Get current authenticated user
    For practice mode, we'll use a dummy user
    """
    # For practice, return dummy user
    # In production, implement proper JWT authentication
    return {
        "id": 1,
        "username": "practice_user",
        "email": "user@example.com",
        "role": "admin"
    }

# Rate limiting dependency
async def check_rate_limit(
    request: Request,
    redis_client: redis.Redis = Depends(get_redis_client)
) -> None:
    """
    Check rate limit for API requests
    """
    if not settings.RATE_LIMIT_ENABLED:
        return
    
    if redis_client is None:
        return
    
    client_ip = request.client.host
    key = f"rate_limit:{client_ip}"
    
    current = redis_client.get(key)
    
    if current is None:
        redis_client.setex(key, settings.RATE_LIMIT_PERIOD, 1)
    else:
        current = int(current)
        if current >= settings.RATE_LIMIT_REQUESTS:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded. Max {settings.RATE_LIMIT_REQUESTS} requests per {settings.RATE_LIMIT_PERIOD} seconds"
            )
        redis_client.incr(key)

# File validation dependency
async def validate_file_size(file_size: int) -> None:
    """
    Validate file size
    """
    if file_size > settings.MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds maximum allowed size of {settings.MAX_FILE_SIZE / 1024 / 1024}MB"
        )

def get_allowed_extensions() -> list:
    """
    Get list of allowed file extensions
    """
    return settings.ALLOWED_EXTENSIONS

# Pagination parameters
from typing import Optional
from pydantic import BaseModel

class PaginationParams(BaseModel):
    """
    Pagination parameters for list endpoints
    """
    page: int = 1
    page_size: int = 20
    sort_by: Optional[str] = None
    sort_order: str = "desc"
    
    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size
    
    @property
    def limit(self) -> int:
        return self.page_size

async def get_pagination_params(
    page: int = 1,
    page_size: int = 20,
    sort_by: Optional[str] = None,
    sort_order: str = "desc"
) -> PaginationParams:
    """
    Get pagination parameters from query string
    """
    return PaginationParams(
        page=page,
        page_size=min(page_size, 100),  # Max 100 per page
        sort_by=sort_by,
        sort_order=sort_order
    )

# Cache utilities
@lru_cache(maxsize=128)
def get_settings() -> Settings:
    """
    Get cached settings
    """
    return settings

# WebSocket manager (for real-time updates)
class WebSocketManager:
    """
    Manage WebSocket connections for real-time updates
    """
    def __init__(self):
        self.active_connections: list = []
        self.logger = logging.getLogger(__name__)
    
    async def connect(self, websocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        self.logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def broadcast(self, message: dict):
        """Broadcast message to all connected clients"""
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception as e:
                self.logger.error(f"Failed to send WebSocket message: {e}")
                await self.disconnect(connection)
    
    async def send_personal(self, message: dict, websocket):
        """Send message to specific client"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            self.logger.error(f"Failed to send personal WebSocket message: {e}")

# Global WebSocket manager instance
websocket_manager = WebSocketManager()

# Dependency to get WebSocket manager
def get_websocket_manager() -> WebSocketManager:
    """
    Get WebSocket manager instance
    """
    return websocket_manager

# Export common dependencies
__all__ = [
    "get_db_session",
    "get_redis_client",
    "get_cache_service",
    "get_ocr_factory",
    "get_model_loader",
    "get_document_service",
    "get_extraction_service",
    "get_classification_service",
    "get_fraud_service",
    "get_current_user",
    "check_rate_limit",
    "validate_file_size",
    "get_allowed_extensions",
    "get_pagination_params",
    "get_settings",
    "get_websocket_manager",
    "websocket_manager"
]