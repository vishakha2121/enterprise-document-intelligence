"""
Fraud Log Model
Stores fraud detection results and alerts
"""

from sqlalchemy import Column, Integer, String, ForeignKey, DateTime, Float, JSON, Boolean, Text
from sqlalchemy.orm import relationship
from datetime import datetime

from app.database.base import Base

class FraudLog(Base):
    """Fraud detection log model"""
    
    __tablename__ = "fraud_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    
    # Document reference
    document_id = Column(Integer, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    
    # Fraud detection results
    risk_score = Column(Float, nullable=False, default=0.0)  # 0-1 scale
    risk_level = Column(String(20), nullable=False)  # low, medium, high, critical
    
    fraud_type = Column(String(50), nullable=True)  # amount_mismatch, document_tampering, duplicate, etc.
    fraud_subtype = Column(String(50), nullable=True)
    
    # Detection details
    detection_methods = Column(JSON, default=list, nullable=False)  # List of methods used
    evidence = Column(JSON, default=list, nullable=False)  # List of evidence items
    
    # Rule violations
    rule_violations = Column(JSON, default=list, nullable=True)  # Which rules were violated
    
    # Anomaly details
    anomalies = Column(JSON, default=list, nullable=True)  # Detected anomalies
    
    # Alert status
    alert_status = Column(String(20), default="active", nullable=False)  # active, resolved, false_positive
    
    # Resolution details
    resolved_at = Column(DateTime, nullable=True)
    resolved_by = Column(Integer, nullable=True)  # user_id who resolved
    resolution_notes = Column(Text, nullable=True)
    
    # Processing metrics
    processing_time_ms = Column(Integer, nullable=False, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)
    
    # Relationships
    document = relationship("Document", back_populates="fraud_logs")
    
    def __repr__(self):
        return f"<FraudLog(id={self.id}, document_id={self.document_id}, risk_score={self.risk_score}, risk_level='{self.risk_level}')>"
    
    def to_dict(self) -> dict:
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "document_id": self.document_id,
            "risk_score": self.risk_score,
            "risk_level": self.risk_level,
            "fraud_type": self.fraud_type,
            "detection_methods": self.detection_methods,
            "evidence": self.evidence,
            "alert_status": self.alert_status,
            "resolution_notes": self.resolution_notes,
            "processing_time_ms": self.processing_time_ms,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None
        }
    
    def is_high_risk(self) -> bool:
        """Check if this is a high risk fraud"""
        return self.risk_level in ["high", "critical"]
    
    def is_resolved(self) -> bool:
        """Check if alert is resolved"""
        return self.alert_status in ["resolved", "false_positive"]