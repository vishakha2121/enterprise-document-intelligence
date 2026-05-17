"""
Pytest Configuration and Fixtures
Shared fixtures for all tests
"""

import pytest
import asyncio
from typing import AsyncGenerator, Generator
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import NullPool
import tempfile
import shutil
from pathlib import Path
import sys
from unittest.mock import Mock, AsyncMock

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.main import app
from app.database.base import Base
from app.database.session import get_db
from app.config import settings
from app.services.cache_service import CacheService
from app.core.ocr.ocr_factory import OCRFactory
from app.core.nlp.model_loader import ModelLoader


# Test database URL (SQLite for testing)
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def test_engine():
    """Create test database engine"""
    engine = create_async_engine(
        TEST_DATABASE_URL,
        echo=False,
        poolclass=NullPool,
    )
    
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    yield engine
    
    # Drop tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture
async def db_session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Create test database session"""
    async_session = async_sessionmaker(
        test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    
    async with async_session() as session:
        yield session
        await session.rollback()
        await session.close()


@pytest.fixture
def client(db_session):
    """Create test client with mocked DB session"""
    
    async def override_get_db():
        yield db_session
    
    app.dependency_overrides[get_db] = override_get_db
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def mock_cache_service():
    """Create mock cache service"""
    cache = Mock(spec=CacheService)
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock(return_value=True)
    cache.delete = AsyncMock(return_value=True)
    cache.exists = AsyncMock(return_value=False)
    return cache


@pytest.fixture
def mock_ocr_factory():
    """Create mock OCR factory"""
    ocr = Mock(spec=OCRFactory)
    ocr.extract_text = AsyncMock(return_value={
        "success": True,
        "text": "Test extracted text from document",
        "confidence": 0.95,
        "processing_time_ms": 100
    })
    ocr.get_available_providers = Mock(return_value={
        "tesseract": True,
        "gemini": False
    })
    return ocr


@pytest.fixture
def mock_model_loader():
    """Create mock model loader"""
    loader = Mock(spec=ModelLoader)
    loader.load_model = AsyncMock(return_value=Mock())
    loader.get_classifier = AsyncMock(return_value=Mock())
    loader.get_ner_extractor = AsyncMock(return_value=Mock())
    loader.is_model_loaded = Mock(return_value=True)
    return loader


@pytest.fixture
def sample_document_data():
    """Sample document data for testing"""
    return {
        "filename": "test_invoice.pdf",
        "title": "Test Invoice",
        "description": "Test invoice for unit testing",
        "file_size": 102400,
        "file_type": "application/pdf",
        "document_type": "invoice"
    }


@pytest.fixture
def sample_extracted_data():
    """Sample extracted data for testing"""
    return {
        "invoice_number": "INV-2024-001",
        "invoice_date": "2024-01-15",
        "due_date": "2024-02-15",
        "vendor_name": "Test Vendor Pvt Ltd",
        "vendor_gst": "27AAACT1234F1Z",
        "customer_name": "Test Customer",
        "subtotal": 10000.00,
        "tax_amount": 1800.00,
        "total_amount": 11800.00,
        "currency": "INR",
        "line_items": [
            {
                "serial_no": "1",
                "description": "Test Product",
                "quantity": 10,
                "unit_price": 1000.00,
                "amount": 10000.00
            }
        ]
    }


@pytest.fixture
def sample_fraud_result():
    """Sample fraud detection result"""
    return {
        "success": True,
        "is_fraudulent": False,
        "risk_score": 0.15,
        "risk_level": "low",
        "fraud_type": None,
        "evidence": [],
        "risk_factors": []
    }


@pytest.fixture
def temp_upload_dir():
    """Create temporary upload directory for tests"""
    temp_dir = tempfile.mkdtemp()
    temp_path = Path(temp_dir)
    
    # Override settings
    settings.UPLOAD_DIR = temp_path / "uploads"
    settings.PROCESSED_DIR = temp_path / "processed"
    settings.TEMP_DIR = temp_path / "temp"
    
    settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    settings.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)
    
    yield temp_path
    
    # Cleanup
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def sample_pdf_content():
    """Create sample PDF content for testing"""
    # Simple valid PDF structure (minimal)
    pdf_content = b'%PDF-1.4\n1 0 obj\n<</Type/Catalog/Pages 2 0 R>>\nendobj\n2 0 obj\n<</Type/Pages/Kids[3 0 R]/Count 1>>\nendobj\n3 0 obj\n<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>\nendobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\ntrailer\n<</Size 4/Root 1 0 R>>\nstartxref\n185\n%%EOF'
    return pdf_content


@pytest.fixture
def auth_headers():
    """Authentication headers for tests"""
    return {
        "Authorization": "Bearer test_api_key_12345"
    }


@pytest.fixture
def current_user():
    """Mock current user for tests"""
    return {
        "id": 1,
        "username": "test_user",
        "email": "test@example.com",
        "role": "admin",
        "is_active": True
    }


@pytest.fixture
def mock_redis_client():
    """Mock Redis client for testing"""
    redis_mock = Mock()
    redis_mock.get = AsyncMock(return_value=None)
    redis_mock.set = AsyncMock(return_value=True)
    redis_mock.delete = AsyncMock(return_value=1)
    redis_mock.ping = AsyncMock(return_value=True)
    redis_mock.flushdb = AsyncMock(return_value=True)
    return redis_mock


@pytest.fixture
def async_return():
    """Helper to create async return values"""
    def _async_return(value):
        async def wrapper():
            return value
        return wrapper()
    return _async_return