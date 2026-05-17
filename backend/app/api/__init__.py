"""
API Package
Contains all API routes and models for the Document Intelligence Platform
"""

from app.api.routes import (
    documents,
    extraction,
    classification,
    fraud,
    dashboard,
    health
)

__all__ = [
    "documents",
    "extraction",
    "classification",
    "fraud",
    "dashboard",
    "health"
]