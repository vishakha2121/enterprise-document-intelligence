"""
Pydantic Response Models
Response schemas for API endpoints
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional, List, Dict, Any, Generic, TypeVar
from datetime import datetime
from enum import Enum

# Generic type for API responses
T = TypeVar('T')

# Enum for response status
class ResponseStatus(str, Enum):
    """Response status enumeration"""
    SUCCESS = "success"
    ERROR = "error"
    WARNING = "warning"

# Base Response Models
class APIResponse(BaseModel, Generic[T]):
    """Generic API response wrapper"""
    success: bool = Field(..., description="Whether the request was successful")
    message: str = Field(..., description="Response message")
    data: Optional[T] = Field(None, description="Response data")
    errors: Optional[List[Dict[str, Any]]] = Field(None, description="Error details if any")
    status_code: int = Field(200, description="HTTP status code")
    timestamp: datetime = Field(default_factory=datetime.now, description="Response timestamp")
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "message": "Operation completed successfully",
                "data": {},
                "status_code": 200,
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }

class HealthResponse(BaseModel):
    """Health check response"""
    status: str = Field(..., description="Health status")
    service: str = Field(..., description="Service name")
    version: str = Field(..., description="API version")
    timestamp: datetime = Field(default_factory=datetime.now)
    environment: str = Field(..., description="Environment (development/production)")

# Document Models
class DocumentResponse(BaseModel):
    """Document information response"""
    id: int = Field(..., description="Document ID")
    filename: str = Field(..., description="Original filename")
    title: Optional[str] = Field(None, description="Document title")
    description: Optional[str] = Field(None, description="Document description")
    file_size: int = Field(..., description="File size in bytes")
    file_type: str = Field(..., description="MIME type")
    document_type: Optional[str] = Field(None, description="Classified document type")
    status: str = Field(..., description="Processing status")
    user_id: int = Field(..., description="Owner user ID")
    tags: List[str] = Field(default_factory=list, description="Document tags")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    thumbnail_url: Optional[str] = Field(None, description="Thumbnail URL")
    download_url: Optional[str] = Field(None, description="Download URL")
    preview_url: Optional[str] = Field(None, description="Preview URL")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    processed_at: Optional[datetime] = Field(None, description="Processing completion timestamp")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "filename": "invoice_001.pdf",
                "title": "Invoice January 2024",
                "file_size": 245760,
                "file_type": "application/pdf",
                "document_type": "invoice",
                "status": "processed",
                "user_id": 1,
                "tags": ["invoice", "january", "2024"],
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:35:00Z"
            }
        }

class DocumentListResponse(BaseModel):
    """Paginated list of documents"""
    items: List[DocumentResponse] = Field(..., description="List of documents")
    total: int = Field(..., description="Total number of documents")
    page: int = Field(..., description="Current page number")
    page_size: int = Field(..., description="Items per page")
    total_pages: int = Field(..., description="Total number of pages")
    
    class Config:
        from_attributes = True

class UploadResponse(BaseModel):
    """Document upload response"""
    document_id: int = Field(..., description="ID of uploaded document")
    filename: str = Field(..., description="Original filename")
    status: str = Field(..., description="Upload status")
    upload_url: Optional[str] = Field(None, description="URL to access document")
    message: str = Field("Document uploaded successfully", description="Success message")
    
    class Config:
        json_schema_extra = {
            "example": {
                "document_id": 123,
                "filename": "invoice.pdf",
                "status": "uploaded",
                "upload_url": "/api/v1/documents/123",
                "message": "Document uploaded successfully"
            }
        }

# Extraction Models
class ExtractedField(BaseModel):
    """Individual extracted field"""
    field_name: str = Field(..., description="Name of the field")
    value: Any = Field(..., description="Extracted value")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    source: str = Field(..., description="Source of extraction (OCR/NER/Gemini)")
    position: Optional[Dict[str, int]] = Field(None, description="Position in document")
    
    class Config:
        json_schema_extra = {
            "example": {
                "field_name": "invoice_number",
                "value": "INV-2024-001",
                "confidence": 0.95,
                "source": "NER"
            }
        }

class ExtractionResponse(BaseModel):
    """Data extraction response"""
    id: int = Field(..., description="Extraction ID")
    document_id: int = Field(..., description="Document ID")
    extraction_type: str = Field(..., description="Type of extraction performed")
    extracted_data: Dict[str, Any] = Field(..., description="Extracted structured data")
    fields: List[ExtractedField] = Field(..., description="List of extracted fields with confidence")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Overall confidence")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    ocr_text: Optional[str] = Field(None, description="Raw OCR text (if requested)")
    status: str = Field(..., description="Extraction status")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "document_id": 123,
                "extraction_type": "full",
                "extracted_data": {
                    "invoice_number": "INV-2024-001",
                    "total_amount": 1500.00,
                    "date": "2024-01-15"
                },
                "confidence_score": 0.92,
                "processing_time_ms": 2345,
                "status": "completed",
                "created_at": "2024-01-15T10:35:00Z"
            }
        }

class ExtractionListResponse(BaseModel):
    """List of extraction results"""
    extractions: List[ExtractionResponse]
    total: int
    document_id: int

# Classification Models
class ClassificationResult(BaseModel):
    """Individual classification result"""
    document_type: str = Field(..., description="Classified document type")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    model_used: str = Field(..., description="Model used for classification")
    
    class Config:
        json_schema_extra = {
            "example": {
                "document_type": "invoice",
                "confidence": 0.94,
                "model_used": "bert"
            }
        }

class ClassificationResponse(BaseModel):
    """Document classification response"""
    id: int = Field(..., description="Classification ID")
    document_id: int = Field(..., description="Document ID")
    document_type: str = Field(..., description="Primary classified type")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    top_predictions: List[ClassificationResult] = Field(..., description="Top K predictions")
    model_version: str = Field(..., description="Model version used")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    class Config:
        from_attributes = True

class BatchClassificationResponse(BaseModel):
    """Batch classification response"""
    total_documents: int = Field(..., description="Total documents processed")
    results: List[ClassificationResponse] = Field(..., description="Classification results")
    summary: Dict[str, Any] = Field(..., description="Summary statistics")
    failed_ids: List[int] = Field(default_factory=list, description="Failed document IDs")

# Fraud Detection Models
class FraudEvidence(BaseModel):
    """Evidence for fraud detection"""
    type: str = Field(..., description="Type of evidence")
    description: str = Field(..., description="Evidence description")
    severity: str = Field(..., description="Severity level (low, medium, high)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Evidence confidence")
    location: Optional[str] = Field(None, description="Location in document")
    
    class Config:
        json_schema_extra = {
            "example": {
                "type": "amount_anomaly",
                "description": "Total amount doesn't match line items sum",
                "severity": "high",
                "confidence": 0.95
            }
        }

class FraudCheckResponse(BaseModel):
    """Fraud detection response"""
    id: int = Field(..., description="Fraud check ID")
    document_id: int = Field(..., description="Document ID")
    is_fraudulent: bool = Field(..., description="Whether fraud was detected")
    risk_score: float = Field(..., ge=0.0, le=1.0, description="Overall risk score")
    risk_level: str = Field(..., description="Risk level (low, medium, high, critical)")
    fraud_type: Optional[str] = Field(None, description="Type of fraud detected")
    evidence: List[FraudEvidence] = Field(..., description="Evidence of fraud")
    rule_matches: List[str] = Field(..., description="Matched fraud rules")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "document_id": 123,
                "is_fraudulent": True,
                "risk_score": 0.89,
                "risk_level": "high",
                "fraud_type": "document_tampering",
                "evidence": [],
                "processing_time_ms": 1234,
                "created_at": "2024-01-15T10:36:00Z"
            }
        }

class FraudAlertResponse(BaseModel):
    """Fraud alert response"""
    id: int = Field(..., description="Alert ID")
    document_id: int = Field(..., description="Document ID")
    fraud_check_id: int = Field(..., description="Associated fraud check ID")
    severity: str = Field(..., description="Alert severity")
    message: str = Field(..., description="Alert message")
    status: str = Field(..., description="Alert status (active, resolved, false_positive)")
    resolved_at: Optional[datetime] = Field(None, description="Resolution timestamp")
    resolved_by: Optional[int] = Field(None, description="User who resolved the alert")
    resolution_notes: Optional[str] = Field(None, description="Resolution notes")
    created_at: datetime = Field(..., description="Creation timestamp")
    
    class Config:
        from_attributes = True

class FraudStatsResponse(BaseModel):
    """Fraud detection statistics"""
    total_checks: int = Field(..., description="Total fraud checks performed")
    fraud_detected: int = Field(..., description="Documents with fraud detected")
    suspicious_count: int = Field(..., description="Suspicious documents count")
    clean_count: int = Field(..., description="Clean documents count")
    high_risk_count: int = Field(..., description="High risk documents count")
    medium_risk_count: int = Field(..., description="Medium risk documents count")
    low_risk_count: int = Field(..., description="Low risk documents count")
    average_risk_score: float = Field(..., description="Average risk score")
    fraud_by_type: Dict[str, int] = Field(..., description="Fraud counts by type")
    fraud_timeline: List[Dict[str, Any]] = Field(..., description="Fraud detection timeline")
    detection_rate: float = Field(..., description="Overall detection rate")
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_checks": 1000,
                "fraud_detected": 45,
                "suspicious_count": 80,
                "clean_count": 875,
                "high_risk_count": 12,
                "average_risk_score": 0.15,
                "detection_rate": 96.5
            }
        }

# Export Models
class ExportResponse(BaseModel):
    """Export response"""
    format: str = Field(..., description="Export format")
    data: Any = Field(..., description="Exported data")
    filename: str = Field(..., description="Suggested filename")
    download_url: Optional[str] = Field(None, description="URL to download exported file")
    expires_at: Optional[datetime] = Field(None, description="Download URL expiry")
    
    class Config:
        json_schema_extra = {
            "example": {
                "format": "json",
                "data": {},
                "filename": "extraction_export_20240115.json",
                "download_url": "/api/v1/extraction/download/file_123.json"
            }
        }

# Error Models
class ErrorDetail(BaseModel):
    """Detailed error information"""
    field: Optional[str] = Field(None, description="Field that caused the error")
    message: str = Field(..., description="Error message")
    code: str = Field(..., description="Error code")
    
    class Config:
        json_schema_extra = {
            "example": {
                "field": "document_id",
                "message": "Document not found",
                "code": "DOCUMENT_NOT_FOUND"
            }
        }

class ErrorResponse(BaseModel):
    """Standard error response"""
    success: bool = Field(False, description="Always false for errors")
    message: str = Field(..., description="Error message")
    errors: List[ErrorDetail] = Field(default_factory=list, description="Detailed errors")
    status_code: int = Field(..., description="HTTP status code")
    timestamp: datetime = Field(default_factory=datetime.now)
    
    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "message": "Validation error",
                "errors": [
                    {"field": "document_id", "message": "Document ID is required", "code": "REQUIRED_FIELD"}
                ],
                "status_code": 400,
                "timestamp": "2024-01-15T10:30:00Z"
            }
        }

# Webhook Models
class WebhookResponse(BaseModel):
    """Webhook configuration response"""
    id: int
    url: HttpUrl
    events: List[str]
    active: bool
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True

class WebhookDeliveryResponse(BaseModel):
    """Webhook delivery status"""
    webhook_id: int
    event: str
    payload: Dict[str, Any]
    response_status: Optional[int]
    response_body: Optional[str]
    delivered_at: datetime
    success: bool
    retry_count: int

# Analytics Models
class DashboardStatsResponse(BaseModel):
    """Dashboard statistics response"""
    total_documents: int
    processed_documents: int
    pending_documents: int
    failed_documents: int
    total_extractions: int
    fraud_detected: int
    fraud_rate: float
    classification_accuracy: float
    extraction_accuracy: float
    average_processing_time: float
    storage_used_mb: float
    active_users: int
    documents_by_type: Dict[str, int]
    documents_by_status: Dict[str, int]
    fraud_by_severity: Dict[str, int]
    
    class Config:
        json_schema_extra = {
            "example": {
                "total_documents": 1250,
                "processed_documents": 1180,
                "pending_documents": 70,
                "classification_accuracy": 94.2,
                "extraction_accuracy": 91.5,
                "fraud_detected": 45,
                "fraud_rate": 3.6
            }
        }

class PerformanceMetricsResponse(BaseModel):
    """Performance metrics response"""
    api_response_time_ms: float
    ocr_processing_time_ms: float
    classification_time_ms: float
    extraction_time_ms: float
    fraud_detection_time_ms: float
    cache_hit_rate: float
    error_rate: float
    requests_per_second: float
    timestamp: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "api_response_time_ms": 245,
                "ocr_processing_time_ms": 1800,
                "classification_time_ms": 320,
                "cache_hit_rate": 0.85,
                "error_rate": 0.02
            }
        }

# User Models
class UserResponse(BaseModel):
    """User information response"""
    id: int
    username: str
    email: str
    full_name: Optional[str]
    role: str
    is_active: bool
    created_at: datetime
    last_login: Optional[datetime]
    
    class Config:
        from_attributes = True

class UserStatsResponse(BaseModel):
    """User statistics response"""
    user_id: int
    total_documents_uploaded: int
    total_extractions_performed: int
    total_fraud_checks: int
    average_confidence_score: float
    documents_by_type: Dict[str, int]
    last_active: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": 1,
                "total_documents_uploaded": 245,
                "total_extractions_performed": 398,
                "average_confidence_score": 0.91
            }
        }

# Batch Processing Models
class BatchJobResponse(BaseModel):
    """Batch job status response"""
    job_id: str
    status: str  # pending, running, completed, failed
    total_items: int
    processed_items: int
    successful_items: int
    failed_items: int
    progress_percentage: float
    started_at: datetime
    completed_at: Optional[datetime]
    error_message: Optional[str]
    results_url: Optional[str]
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "batch_123456",
                "status": "running",
                "total_items": 50,
                "processed_items": 25,
                "progress_percentage": 50.0,
                "started_at": "2024-01-15T10:30:00Z"
            }
        }

# Compare Documents Response
class DocumentComparisonResponse(BaseModel):
    """Document comparison response"""
    document_ids: List[int]
    common_fields: List[str]
    differences: Dict[str, Dict[str, Any]]
    similarity_score: float
    comparison_summary: str
    created_at: datetime
    
    class Config:
        json_schema_extra = {
            "example": {
                "document_ids": [123, 124],
                "common_fields": ["total_amount", "date"],
                "similarity_score": 0.85,
                "comparison_summary": "Documents are 85% similar"
            }
        }