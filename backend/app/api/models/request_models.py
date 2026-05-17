"""
Pydantic Request Models
Request validation schemas for API endpoints
"""

from pydantic import BaseModel, Field, validator, HttpUrl
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

# Enums for request validation
class DocumentTypeEnum(str, Enum):
    """Document type enumeration"""
    INVOICE = "invoice"
    CONTRACT = "contract"
    FORM = "form"
    RECEIPT = "receipt"
    REPORT = "report"
    OTHER = "other"

class DocumentStatusEnum(str, Enum):
    """Document processing status"""
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    ARCHIVED = "archived"

class ExtractionTypeEnum(str, Enum):
    """Extraction type enumeration"""
    FULL = "full"
    SPECIFIC_FIELDS = "specific_fields"
    CUSTOM = "custom"

class ExportFormatEnum(str, Enum):
    """Export format enumeration"""
    JSON = "json"
    CSV = "csv"
    XML = "xml"
    ERP_READY = "erp_ready"

class ModelTypeEnum(str, Enum):
    """Model type for classification"""
    BERT = "bert"
    RULE_BASED = "rule_based"
    HYBRID = "hybrid"

class FraudCheckTypeEnum(str, Enum):
    """Fraud check types"""
    RULE_BASED = "rule_based"
    ANOMALY = "anomaly"
    DUPLICATE = "duplicate"
    SIGNATURE = "signature"
    KEYWORD = "keyword"
    ALL = "all"

# Request Models
class DocumentUploadRequest(BaseModel):
    """Request model for document upload"""
    title: Optional[str] = Field(None, max_length=255, description="Document title")
    description: Optional[str] = Field(None, max_length=1000, description="Document description")
    document_type: Optional[DocumentTypeEnum] = Field(None, description="Document type hint")
    tags: Optional[List[str]] = Field(default_factory=list, description="Document tags")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    
    @validator('tags')
    def validate_tags(cls, v):
        if len(v) > 10:
            raise ValueError('Maximum 10 tags allowed')
        return v

class DocumentUpdateRequest(BaseModel):
    """Request model for updating document metadata"""
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = Field(None, max_length=1000)
    document_type: Optional[DocumentTypeEnum] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None
    status: Optional[DocumentStatusEnum] = None

class ExtractionRequest(BaseModel):
    """Request model for data extraction"""
    fields: Optional[List[str]] = Field(
        None,
        description="Specific fields to extract (e.g., ['amount', 'date', 'invoice_number'])"
    )
    extraction_type: ExtractionTypeEnum = Field(
        default=ExtractionTypeEnum.FULL,
        description="Type of extraction to perform"
    )
    confidence_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum confidence threshold for extracted data"
    )
    include_ocr_text: bool = Field(
        default=False,
        description="Include raw OCR text in response"
    )
    use_gemini_fallback: bool = Field(
        default=True,
        description="Use Gemini API as fallback if Tesseract fails"
    )
    
    @validator('fields')
    def validate_fields(cls, v):
        if v and len(v) > 50:
            raise ValueError('Maximum 50 fields can be requested')
        return v

class ExportRequest(BaseModel):
    """Request model for exporting extraction data"""
    format: ExportFormatEnum = Field(
        default=ExportFormatEnum.JSON,
        description="Export format"
    )
    include_metadata: bool = Field(
        default=True,
        description="Include document metadata in export"
    )
    include_confidence_scores: bool = Field(
        default=True,
        description="Include confidence scores for extracted fields"
    )
    erp_system: Optional[str] = Field(
        None,
        description="ERP system format (if format='erp_ready')"
    )
    fields: Optional[List[str]] = Field(
        None,
        description="Specific fields to export (export all if None)"
    )
    
    @validator('erp_system')
    def validate_erp_system(cls, v, values):
        if values.get('format') == ExportFormatEnum.ERP_READY and not v:
            raise ValueError('erp_system is required when format is erp_ready')
        return v

class ClassificationRequest(BaseModel):
    """Request model for document classification"""
    model_type: ModelTypeEnum = Field(
        default=ModelTypeEnum.HYBRID,
        description="Model to use for classification"
    )
    confidence_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Minimum confidence for classification"
    )
    return_top_k: int = Field(
        default=3,
        ge=1,
        le=10,
        description="Return top K classifications with scores"
    )
    use_cache: bool = Field(
        default=True,
        description="Use cached classification if available"
    )

class BatchClassificationRequest(BaseModel):
    """Request model for batch document classification"""
    document_ids: List[int] = Field(
        ...,
        description="List of document IDs to classify",
        min_items=1,
        max_items=100
    )
    model_type: ModelTypeEnum = Field(default=ModelTypeEnum.HYBRID)
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)
    
    @validator('document_ids')
    def validate_document_ids(cls, v):
        if len(set(v)) != len(v):
            raise ValueError('Duplicate document IDs found')
        return v

class FraudCheckRequest(BaseModel):
    """Request model for fraud detection"""
    check_types: List[FraudCheckTypeEnum] = Field(
        default=[FraudCheckTypeEnum.ALL],
        description="Types of fraud checks to perform"
    )
    threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Sensitivity threshold for fraud detection"
    )
    include_evidence: bool = Field(
        default=True,
        description="Include evidence for fraud detection"
    )
    compare_with_previous: bool = Field(
        default=True,
        description="Compare with previous versions of document"
    )
    
    @validator('check_types')
    def validate_check_types(cls, v):
        if FraudCheckTypeEnum.ALL in v and len(v) > 1:
            raise ValueError("When 'ALL' is selected, no other check types should be specified")
        return v

class FraudReportRequest(BaseModel):
    """Request model for generating fraud report"""
    format: ExportFormatEnum = Field(default=ExportFormatEnum.JSON)
    include_details: bool = Field(default=True)
    include_recommendations: bool = Field(default=True)
    severity_filter: Optional[str] = Field(
        None,
        description="Filter by severity (low, medium, high, critical)"
    )

class PaginationParams(BaseModel):
    """Pagination parameters for list endpoints"""
    page: int = Field(default=1, ge=1, description="Page number")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")
    sort_by: Optional[str] = Field(None, description="Field to sort by")
    sort_order: str = Field(default="desc", regex="^(asc|desc)$", description="Sort order")
    
    @property
    def offset(self) -> int:
        """Calculate SQL offset"""
        return (self.page - 1) * self.page_size
    
    @property
    def limit(self) -> int:
        """Get SQL limit"""
        return self.page_size

class SearchRequest(BaseModel):
    """Request model for searching documents"""
    query: str = Field(..., min_length=1, max_length=200, description="Search query")
    document_types: Optional[List[DocumentTypeEnum]] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    statuses: Optional[List[DocumentStatusEnum]] = None
    tags: Optional[List[str]] = None
    pagination: PaginationParams = Field(default_factory=PaginationParams)

class FeedbackRequest(BaseModel):
    """Request model for user feedback"""
    document_id: int
    classification_id: Optional[int] = None
    extraction_id: Optional[int] = None
    correct_type: Optional[str] = None
    correct_fields: Optional[Dict[str, Any]] = None
    is_fraud: Optional[bool] = None
    comments: Optional[str] = Field(None, max_length=500)
    rating: Optional[int] = Field(None, ge=1, le=5)

class WebhookRequest(BaseModel):
    """Request model for webhook configuration"""
    url: HttpUrl = Field(..., description="Webhook URL")
    events: List[str] = Field(
        ...,
        description="Events to trigger webhook (document.processed, fraud.detected, etc.)"
    )
    secret: Optional[str] = Field(None, min_length=16, description="Webhook secret for signing")
    active: bool = Field(default=True)
    
    @validator('events')
    def validate_events(cls, v):
        valid_events = [
            'document.uploaded',
            'document.processed',
            'document.failed',
            'extraction.completed',
            'classification.completed',
            'fraud.detected',
            'fraud.resolved'
        ]
        for event in v:
            if event not in valid_events:
                raise ValueError(f'Invalid event: {event}. Valid events: {valid_events}')
        return v

class TrainingRequest(BaseModel):
    """Request model for model training"""
    dataset_id: str = Field(..., description="Dataset ID for training")
    model_type: ModelTypeEnum = Field(default=ModelTypeEnum.BERT)
    epochs: int = Field(default=3, ge=1, le=50)
    batch_size: int = Field(default=32, ge=8, le=128)
    learning_rate: float = Field(default=2e-5, ge=1e-6, le=1e-3)
    validation_split: float = Field(default=0.2, ge=0.1, le=0.3)
    use_gpu: bool = Field(default=False)  # CPU only for practice

class CompareDocumentsRequest(BaseModel):
    """Request model for comparing multiple documents"""
    document_ids: List[int] = Field(..., min_items=2, max_items=10)
    compare_fields: List[str] = Field(
        default_factory=list,
        description="Specific fields to compare"
    )
    highlight_differences: bool = Field(default=True)
    
    @validator('document_ids')
    def validate_unique_ids(cls, v):
        if len(set(v)) != len(v):
            raise ValueError('Document IDs must be unique')
        return 