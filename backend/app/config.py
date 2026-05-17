"""
Application Configuration Management
Using Pydantic for settings validation
"""

from typing import List, Optional
from pydantic import BaseSettings, Field, validator
import os
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv

# Load .env file
load_dotenv()

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables
    """
    
    # Application Settings
    APP_NAME: str = "Enterprise AI Document Intelligence"
    APP_VERSION: str = "1.0.0"
    ENVIRONMENT: str = Field("development", env="ENVIRONMENT")
    DEBUG: bool = Field(True, env="DEBUG")
    HOST: str = Field("0.0.0.0", env="HOST")
    PORT: int = Field(8000, env="PORT")
    LOG_LEVEL: str = Field("INFO", env="LOG_LEVEL")
    
    # Security
    SECRET_KEY: str = Field("your-secret-key-change-this", env="SECRET_KEY")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ]
    ALLOWED_HOSTS: List[str] = ["*"]
    
    # Database Settings
    DATABASE_URL: str = Field(
        "postgresql://postgres:postgres@localhost:5432/docai",
        env="DATABASE_URL"
    )
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30
    DATABASE_ECHO: bool = False
    
    # Redis Settings
    REDIS_URL: str = Field("redis://localhost:6379", env="REDIS_URL")
    REDIS_CACHE_TTL: int = 3600  # 1 hour
    
    # Celery Settings
    CELERY_BROKER_URL: str = Field("redis://localhost:6379/0", env="CELERY_BROKER_URL")
    CELERY_RESULT_BACKEND: str = Field("redis://localhost:6379/1", env="CELERY_RESULT_BACKEND")
    
    # AWS S3 Settings (Optional - for production)
    AWS_ACCESS_KEY_ID: Optional[str] = Field(None, env="AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = Field(None, env="AWS_SECRET_ACCESS_KEY")
    AWS_S3_BUCKET: Optional[str] = Field(None, env="AWS_S3_BUCKET")
    AWS_REGION: str = Field("us-east-1", env="AWS_REGION")
    USE_S3_STORAGE: bool = False  # Use local storage by default for practice
    
    # Gemini API Settings
    GEMINI_API_KEY: Optional[str] = Field(None, env="GEMINI_API_KEY")
    USE_GEMINI_FALLBACK: bool = True  # Use Gemini when Tesseract fails
    
    # OCR Settings
    TESSERACT_PATH: str = Field("tesseract", env="TESSERACT_PATH")
    OCR_LANGUAGE: str = "eng"
    OCR_CONFIG: dict = {
        "psm": 3,  # Automatic page segmentation
        "oem": 3,  # Default OCR Engine Mode
    }
    
    # Document Processing Settings
    MAX_FILE_SIZE: int = 10 * 1024 * 1024  # 10MB
    ALLOWED_EXTENSIONS: List[str] = [".pdf", ".jpg", ".jpeg", ".png", ".tiff"]
    ALLOWED_MIME_TYPES: List[str] = [
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/tiff"
    ]
    
    # BERT Model Settings
    BERT_MODEL_NAME: str = "bert-base-uncased"
    BERT_MODEL_PATH: str = "models/bert/document_classifier"
    NER_MODEL_PATH: str = "models/bert/ner_model"
    CLASSIFICATION_THRESHOLD: float = 0.7
    MAX_SEQUENCE_LENGTH: int = 512
    BATCH_SIZE: int = 32
    
    # Fraud Detection Settings
    FRAUD_DETECTION_ENABLED: bool = True
    ANOMALY_THRESHOLD: float = 2.5  # Standard deviations
    DUPLICATE_SIMILARITY_THRESHOLD: float = 0.95
    SUSPICIOUS_KEYWORDS: List[str] = [
        "urgent", "confidential", "do not share", "final version",
        "unauthorized", "modified", "fake", "fraud"
    ]
    
    # File Storage
    UPLOAD_DIR: Path = Path("uploads")
    PROCESSED_DIR: Path = Path("uploads/processed")
    TEMP_DIR: Path = Path("uploads/temp")
    
    # Cache Settings
    ENABLE_REDIS_CACHE: bool = True
    CACHE_DOCUMENT_EXTRACTIONS: bool = True
    EXTRACTION_CACHE_TTL: int = 86400  # 24 hours
    
    # Rate Limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_REQUESTS: int = 100
    RATE_LIMIT_PERIOD: int = 60  # seconds
    
    # Async Processing
    ASYNC_PROCESSING: bool = True
    MAX_CONCURRENT_TASKS: int = 5
    
    @validator("CORS_ORIGINS", pre=True)
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",")]
        return v
    
    @validator("ALLOWED_HOSTS", pre=True)
    def parse_allowed_hosts(cls, v):
        if isinstance(v, str):
            return [host.strip() for host in v.split(",")]
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"

# Create settings instance
settings = Settings()

# Create necessary directories
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)

# Log settings on startup (without sensitive info)
def log_settings():
    """
    Log application settings (without sensitive information)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"Application: {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    logger.info(f"Debug Mode: {settings.DEBUG}")
    logger.info(f"Host: {settings.HOST}:{settings.PORT}")
    logger.info(f"Database: {settings.DATABASE_URL.split('@')[-1] if '@' in settings.DATABASE_URL else 'local'}")
    logger.info(f"Redis: {settings.REDIS_URL}")
    logger.info(f"OCR Engine: Tesseract + {'Gemini' if settings.GEMINI_API_KEY else 'No fallback'}")
    logger.info(f"Storage: {'S3' if settings.USE_S3_STORAGE else 'Local'}")
    logger.info(f"Fraud Detection: {'Enabled' if settings.FRAUD_DETECTION_ENABLED else 'Disabled'}")

# Function to validate critical settings
def validate_settings():
    """
    Validate critical settings before starting application
    """
    import logging
    logger = logging.getLogger(__name__)
    
    errors = []
    
    # Check if SECRET_KEY is default
    if settings.SECRET_KEY == "your-secret-key-change-this":
        logger.warning("Using default SECRET_KEY. Please change in production!")
    
    # Check if Gemini API key is present
    if settings.USE_GEMINI_FALLBACK and not settings.GEMINI_API_KEY:
        logger.warning("GEMINI_API_KEY not set. Gemini fallback disabled.")
    
    # Check if upload directories exist
    if not settings.UPLOAD_DIR.exists():
        errors.append(f"Upload directory {settings.UPLOAD_DIR} does not exist")
    
    if errors:
        for error in errors:
            logger.error(error)
        raise RuntimeError("Configuration validation failed")
    
    logger.info("Configuration validation passed")