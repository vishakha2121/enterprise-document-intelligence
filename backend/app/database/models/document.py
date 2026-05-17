"""
Document Model
Stores document metadata and file information
"""

from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime, Boolean, Float, JSON
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database.base import Base, TimestampMixin

class Document(Base, TimestampMixin):
    """Document metadata model"""
    
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Basic info
    filename = Column(String(255), nullable=False)
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    
    # File info
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)  # bytes
    file_type = Column(String(100), nullable=False)  # MIME type
    file_hash = Column(String(64), nullable=True)  # SHA-256 for deduplication
    
    # Document classification
    document_type = Column(String(50), nullable=True)  # invoice, contract, form, etc.
    classification_confidence = Column(Float, nullable=True)
    classification_model = Column(String(50), nullable=True)
    
    # Processing status
    status = Column(String(50), default="uploaded", nullable=False)
    # Status values: uploaded, processing, processed, failed, archived, deleted
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    processed_at = Column(DateTime, nullable=True)
    archived_at = Column(DateTime, nullable=True)
    
    # Metadata
    tags = Column(JSON, default=list, nullable=False)  # List of tags
    metadata = Column(JSON, default=dict, nullable=False)  # Custom metadata
    
    # Soft delete
    is_deleted = Column(Boolean, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)
    
    # Foreign keys
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Relationships
    user = relationship("User", back_populates="documents")
    extraction_results = relationship("ExtractionResult", back_populates="document", cascade="all, delete-orphan")
    fraud_logs = relationship("FraudLog", back_populates="document", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="document")
    
    def __repr__(self):
        return f"<Document(id={self.id}, filename='{self.filename}', status='{self.status}', user_id={self.user_id})>"
    
    def to_dict(self) -> dict:
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "filename": self.filename,
            "title": self.title,
            "description": self.description,
            "file_size": self.file_size,
            "file_type": self.file_type,
            "document_type": self.document_type,
            "classification_confidence": self.classification_confidence,
            "status": self.status,
            "error_message": self.error_message,
            "tags": self.tags,
            "metadata": self.metadata,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
            "download_url": f"/api/v1/documents/{self.id}/download",
            "preview_url": f"/api/v1/documents/{self.id}/preview"
        }