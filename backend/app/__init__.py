"""
Enterprise AI Document Intelligence Platform
Backend Application Package
"""

__version__ = "1.0.0"
__author__ = "AI/ML Engineer"
__description__ = "Enterprise Document Intelligence Platform with OCR, NLP, and Fraud Detection"

from app.config import settings
from app.database.session import SessionLocal

__all__ = ["settings", "SessionLocal"]