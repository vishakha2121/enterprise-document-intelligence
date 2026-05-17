"""
Custom Exceptions
Application-specific exception classes
"""

from typing import Optional, Dict, Any

class AppException(Exception):
    """Base exception for the application"""
    
    def __init__(
        self,
        message: str,
        error_code: str = "APP_ERROR",
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for API response"""
        return {
            "error": self.error_code,
            "message": self.message,
            "status_code": self.status_code,
            "details": self.details
        }

class DocumentNotFoundError(AppException):
    """Raised when a document is not found"""
    
    def __init__(self, document_id: int = None, message: str = None):
        msg = message or f"Document with ID {document_id} not found" if document_id else "Document not found"
        super().__init__(
            message=msg,
            error_code="DOCUMENT_NOT_FOUND",
            status_code=404
        )

class ExtractionError(AppException):
    """Raised when document extraction fails"""
    
    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(
            message=message,
            error_code="EXTRACTION_ERROR",
            status_code=500,
            details=details
        )

class FraudDetectionError(AppException):
    """Raised when fraud detection fails"""
    
    def __init__(self, message: str, details: Dict[str, Any] = None):
        super().__init__(
            message=message,
            error_code="FRAUD_DETECTION_ERROR",
            status_code=500,
            details=details
        )

class StorageError(AppException):
    """Raised when storage operations fail"""
    
    def __init__(self, message: str, operation: str = None):
        details = {"operation": operation} if operation else None
        super().__init__(
            message=message,
            error_code="STORAGE_ERROR",
            status_code=500,
            details=details
        )

class ValidationError(AppException):
    """Raised when input validation fails"""
    
    def __init__(self, message: str, field: str = None):
        details = {"field": field} if field else None
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            status_code=400,
            details=details
        )

class RateLimitError(AppException):
    """Raised when rate limit is exceeded"""
    
    def __init__(self, message: str = "Rate limit exceeded"):
        super().__init__(
            message=message,
            error_code="RATE_LIMIT_EXCEEDED",
            status_code=429
        )

class AuthenticationError(AppException):
    """Raised when authentication fails"""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(
            message=message,
            error_code="AUTHENTICATION_ERROR",
            status_code=401
        )

class PermissionError(AppException):
    """Raised when user lacks permission"""
    
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            message=message,
            error_code="PERMISSION_DENIED",
            status_code=403
        )

class ConfigurationError(AppException):
    """Raised when configuration is invalid"""
    
    def __init__(self, message: str):
        super().__init__(
            message=message,
            error_code="CONFIGURATION_ERROR",
            status_code=500
        )

class ModelLoadError(AppException):
    """Raised when AI model fails to load"""
    
    def __init__(self, model_name: str, message: str = None):
        msg = message or f"Failed to load model: {model_name}"
        super().__init__(
            message=msg,
            error_code="MODEL_LOAD_ERROR",
            status_code=500
        )

class OCRTimeoutError(AppException):
    """Raised when OCR operation times out"""
    
    def __init__(self, message: str = "OCR operation timed out"):
        super().__init__(
            message=message,
            error_code="OCR_TIMEOUT",
            status_code=504
        )

# Exception handlers for FastAPI
def create_exception_handler(status_code: int, error_code: str):
    """Create exception handler for FastAPI"""
    from fastapi.responses import JSONResponse
    from fastapi import Request
    
    async def handler(request: Request, exc: AppException):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": exc.error_code,
                "message": exc.message,
                "details": exc.details
            }
        )
    
    return handler

# FastAPI exception handlers
async def app_exception_handler(request, exc: AppException):
    """Handler for AppException"""
    from fastapi.responses import JSONResponse
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.error_code,
            "message": exc.message,
            "details": exc.details
        }
    )

async def http_exception_handler(request, exc):
    """Handler for HTTPException"""
    from fastapi.responses import JSONResponse
    from fastapi import status
    
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": "HTTP_ERROR",
            "message": exc.detail,
            "status_code": exc.status_code
        }
    )

async def generic_exception_handler(request, exc):
    """Handler for generic exceptions"""
    from fastapi.responses import JSONResponse
    import logging
    
    logger = logging.getLogger(__name__)
    logger.error(f"Unhandled exception: {str(exc)}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": "INTERNAL_SERVER_ERROR",
            "message": "An unexpected error occurred"
        }
    )