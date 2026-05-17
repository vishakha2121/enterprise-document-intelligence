"""
API Models Package
Pydantic models for request and response validation
"""

from app.api.models.request_models import (
    DocumentUploadRequest,
    DocumentUpdateRequest,
    ExtractionRequest,
    ExportRequest,
    ClassificationRequest,
    BatchClassificationRequest,
    FraudCheckRequest,
    FraudReportRequest,
    PaginationParams
)

from app.api.models.response_models import (
    DocumentResponse,
    DocumentListResponse,
    UploadResponse,
    ExtractionResponse,
    ExtractionListResponse,
    ClassificationResponse,
    BatchClassificationResponse,
    FraudCheckResponse,
    FraudAlertResponse,
    FraudStatsResponse,
    ExportResponse,
    APIResponse,
    HealthResponse
)

__all__ = [
    # Request models
    "DocumentUploadRequest",
    "DocumentUpdateRequest",
    "ExtractionRequest",
    "ExportRequest",
    "ClassificationRequest",
    "BatchClassificationRequest",
    "FraudCheckRequest",
    "FraudReportRequest",
    "PaginationParams",
    
    # Response models
    "DocumentResponse",
    "DocumentListResponse",
    "UploadResponse",
    "ExtractionResponse",
    "ExtractionListResponse",
    "ClassificationResponse",
    "BatchClassificationResponse",
    "FraudCheckResponse",
    "FraudAlertResponse",
    "FraudStatsResponse",
    "ExportResponse",
    "APIResponse",
    "HealthResponse"
]