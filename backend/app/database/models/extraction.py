"""
Extraction Result Model
Stores extracted data from documents
"""

from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Float, JSON, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database.base import Base

class ExtractionResult(Base):
    """Extraction result model"""
    
    __tablename__ = "extraction_results"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Document reference
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Extraction details
    extraction_type = Column(String(50), nullable=False)  # full, specific_fields, custom
    extracted_data = Column(JSON, nullable=False, default=dict)
    validated_data = Column(JSON, nullable=True)  # User-corrected data
    
    # Confidence scores
    confidence_score = Column(Float, nullable=False, default=0.0)
    field_confidences = Column(JSON, nullable=True, default=dict)
    
    # OCR text (can be large, optional)
    ocr_text = Column(Text, nullable=True)
    ocr_engine = Column(String(50), nullable=True)  # tesseract, gemini, hybrid
    
    # Processing metrics
    processing_time_ms = Column(Integer, nullable=False, default=0)
    ocr_time_ms = Column(Integer, nullable=True)
    nlp_time_ms = Column(Integer, nullable=True)
    
    # Validation status
    is_validated = Column(Boolean, default=False, nullable=False)
    validated_at = Column(DateTime, nullable=True)
    validated_by = Column(Integer, nullable=True)  # user_id who validated
    
    # Status
    status = Column(String(50), default="completed", nullable=False)
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    
    # Relationships
    document = relationship("Document", back_populates="extraction_results")
    user = relationship("User", back_populates="extractions")
    
    def __repr__(self):
        return f"<ExtractionResult(id={self.id}, document_id={self.document_id}, confidence={self.confidence_score})>"
    
    def to_dict(self) -> dict:
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "extraction_type": self.extraction_type,
            "extracted_data": self.extracted_data,
            "validated_data": self.validated_data,
            "confidence_score": self.confidence_score,
            "field_confidences": self.field_confidences,
            "ocr_engine": self.ocr_engine,
            "processing_time_ms": self.processing_time_ms,
            "is_validated": self.is_validated,
            "validated_at": self.validated_at.isoformat() if self.validated_at else None,
            "status": self.status,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    def get_extracted_field(self, field_name: str) -> any:
        """Get specific extracted field value"""
        return self.extracted_data.get(field_name)
    
    def get_confidence_for_field(self, field_name: str) -> float:
        """Get confidence score for specific field"""
        if self.field_confidences:
            return self.field_confidences.get(field_name, 0.0)
        return self.confidence_score