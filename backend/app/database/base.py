"""
SQLAlchemy Base
Declarative base for all ORM models
"""

from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, DateTime, func
from datetime import datetime

Base = declarative_base()

class TimestampMixin:
    """Mixin for created_at and updated_at timestamps"""
    
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)

class SoftDeleteMixin:
    """Mixin for soft delete functionality"""
    
    is_deleted = Column(DateTime, default=False, nullable=False)
    deleted_at = Column(DateTime, nullable=True)