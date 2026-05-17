"""
Audit Log Model
Tracks all user actions for compliance and debugging
"""

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Text, JSON, BigInteger
from sqlalchemy.orm import relationship
from datetime import datetime
import enum

from app.database.base import Base

class AuditAction(str, enum.Enum):
    """Audit action types"""
    # Document actions
    DOCUMENT_UPLOAD = "document_upload"
    DOCUMENT_DOWNLOAD = "document_download"
    DOCUMENT_DELETE = "document_delete"
    DOCUMENT_UPDATE = "document_update"
    DOCUMENT_VIEW = "document_view"
    
    # Processing actions
    EXTRACTION_START = "extraction_start"
    EXTRACTION_COMPLETE = "extraction_complete"
    CLASSIFICATION_START = "classification_start"
    CLASSIFICATION_COMPLETE = "classification_complete"
    FRAUD_CHECK_START = "fraud_check_start"
    FRAUD_CHECK_COMPLETE = "fraud_check_complete"
    
    # User actions
    USER_LOGIN = "user_login"
    USER_LOGOUT = "user_logout"
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    
    # System actions
    SYSTEM_CONFIG_CHANGE = "system_config_change"
    MODEL_TRAINING = "model_training"
    CACHE_CLEAR = "cache_clear"
    
    # Security actions
    API_KEY_CREATE = "api_key_create"
    API_KEY_REVOKE = "api_key_revoke"
    PERMISSION_CHANGE = "permission_change"

class AuditLog(Base):
    """Audit trail model for compliance"""
    
    __tablename__ = "audit_logs"
    
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    
    # Who
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    username = Column(String(50), nullable=True)  # Denormalized for quick access
    ip_address = Column(String(45), nullable=True)  # IPv4 or IPv6
    user_agent = Column(String(500), nullable=True)
    
    # What
    action = Column(String(50), nullable=False)
    resource_type = Column(String(50), nullable=True)  # document, extraction, user, etc.
    resource_id = Column(Integer, nullable=True)
    resource_name = Column(String(255), nullable=True)
    
    # Details
    details = Column(JSON, default=dict, nullable=False)
    changes = Column(JSON, nullable=True)  # Before/after for updates
    
    # Status
    status = Column(String(20), nullable=False, default="success")  # success, failure, warning
    error_message = Column(Text, nullable=True)
    
    # Performance
    duration_ms = Column(Integer, nullable=True)  # Time taken for action
    
    # Request info
    request_method = Column(String(10), nullable=True)
    request_path = Column(String(500), nullable=True)
    request_query = Column(String(500), nullable=True)
    
    # Compliance
    session_id = Column(String(100), nullable=True)
    correlation_id = Column(String(100), nullable=True)  # For tracing across services
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    
    # Indexes
    __table_args__ = (
        # Indexes can be added via migrations
    )
    
    # Relationships
    user = relationship("User", back_populates="audit_logs")
    document = relationship("Document", back_populates="audit_logs")
    
    def __repr__(self):
        return f"<AuditLog(id={self.id}, user_id={self.user_id}, action='{self.action}', created_at={self.created_at})>"
    
    def to_dict(self) -> dict:
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "username": self.username,
            "action": self.action,
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "resource_name": self.resource_name,
            "details": self.details,
            "status": self.status,
            "error_message": self.error_message,
            "duration_ms": self.duration_ms,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
    
    @classmethod
    def from_request(
        cls,
        request,
        action: str,
        user_id: int = None,
        username: str = None,
        details: dict = None,
        status: str = "success",
        duration_ms: int = None
    ):
        """Create audit log from FastAPI request"""
        return cls(
            user_id=user_id,
            username=username,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
            request_method=request.method,
            request_path=request.url.path,
            request_query=str(request.query_params) if request.query_params else None,
            action=action,
            details=details or {},
            status=status,
            duration_ms=duration_ms
        )
    
    async def save_async(self, db_session):
        """Save audit log asynchronously"""
        db_session.add(self)
        await db_session.commit()