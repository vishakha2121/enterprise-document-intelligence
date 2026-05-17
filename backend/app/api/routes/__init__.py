"""
Routes Package
All API endpoint routes
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