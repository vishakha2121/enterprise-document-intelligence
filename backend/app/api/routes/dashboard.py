"""
Dashboard Routes
Analytics and statistics for document intelligence
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import logging

from app.dependencies import (
    get_db_session,
    get_current_user,
    get_cache_service
)
from app.services.cache_service import CacheService
from app.api.models.response_models import APIResponse

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/stats/overview")
async def get_dashboard_overview(
    days: int = 30,
    db: AsyncSession = Depends(get_db_session),
    cache_service: CacheService = Depends(get_cache_service),
    current_user: dict = Depends(get_current_user)
):
    """
    Get dashboard overview statistics
    """
    cache_key = f"dashboard:overview:{current_user['id']}:{days}"
    
    # Check cache
    if cache_service:
        cached_data = await cache_service.get(cache_key)
        if cached_data:
            return APIResponse(success=True, data=cached_data)
    
    # This would be replaced with actual database queries
    # For now, returning mock data structure
    overview_data = {
        "total_documents": 1250,
        "processed_documents": 1180,
        "pending_documents": 70,
        "failed_documents": 15,
        "total_extractions": 2340,
        "fraud_detected": 45,
        "fraud_rate": 3.6,
        "classification_accuracy": 94.2,
        "extraction_accuracy": 91.5,
        "average_processing_time": 2.3,  # seconds
        "storage_used": 256.5,  # MB
        "active_users": 8,
        "documents_by_type": {
            "invoice": 650,
            "contract": 320,
            "form": 180,
            "other": 100
        },
        "documents_by_status": {
            "uploaded": 70,
            "processing": 25,
            "processed": 1100,
            "failed": 15,
            "archived": 40
        },
        "fraud_by_severity": {
            "critical": 5,
            "high": 12,
            "medium": 18,
            "low": 10
        }
    }
    
    # Cache for 5 minutes
    if cache_service:
        await cache_service.set(cache_key, overview_data, ttl=300)
    
    return APIResponse(success=True, data=overview_data)

@router.get("/stats/daily")
async def get_daily_stats(
    days: int = 7,
    db: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user)
):
    """
    Get daily statistics for the last N days
    """
    # Mock daily data
    daily_stats = []
    today = datetime.now()
    
    for i in range(days):
        date = today - timedelta(days=i)
        daily_stats.append({
            "date": date.strftime("%Y-%m-%d"),
            "documents_uploaded": 25 + (i * 3),
            "documents_processed": 22 + (i * 2),
            "extractions_performed": 45 + (i * 5),
            "fraud_detected": 2 + (i % 3),
            "average_confidence": 0.89 - (i * 0.01)
        })
    
    return APIResponse(success=True, data=daily_stats)

@router.get("/stats/processing-time")
async def get_processing_time_stats(
    days: int = 30,
    db: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user)
):
    """
    Get document processing time statistics
    """
    processing_stats = {
        "average_by_type": {
            "invoice": 2.1,
            "contract": 3.8,
            "form": 1.6,
            "other": 2.3
        },
        "percentiles": {
            "p50": 2.0,
            "p90": 4.5,
            "p95": 6.0,
            "p99": 8.5
        },
        "fastest": 0.8,
        "slowest": 15.2,
        "optimization_score": 87.5
    }
    
    return APIResponse(success=True, data=processing_stats)

@router.get("/stats/ai-performance")
async def get_ai_performance_metrics(
    db: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user)
):
    """
    Get AI model performance metrics
    """
    metrics = {
        "classification_model": {
            "accuracy": 94.2,
            "precision": 93.5,
            "recall": 92.8,
            "f1_score": 93.1,
            "last_trained": "2024-01-15",
            "total_trained_samples": 15000
        },
        "ner_model": {
            "accuracy": 89.7,
            "precision": 88.9,
            "recall": 87.5,
            "f1_score": 88.2,
            "entities_supported": 12
        },
        "fraud_detection_model": {
            "accuracy": 96.3,
            "precision": 94.1,
            "recall": 93.2,
            "f1_score": 93.6,
            "false_positive_rate": 2.1
        },
        "ocr_accuracy": {
            "tesseract": 85.3,
            "gemini": 92.7,
            "hybrid": 94.1
        }
    }
    
    return APIResponse(success=True, data=metrics)

@router.get("/stats/user-activity")
async def get_user_activity(
    days: int = 30,
    db: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user)
):
    """
    Get user activity statistics
    """
    activity = {
        "total_users": 12,
        "active_users_last_7d": 8,
        "active_users_last_30d": 11,
        "documents_per_user_avg": 104,
        "most_active_user": "john.doe@example.com",
        "user_breakdown": {
            "admin": 2,
            "analyst": 5,
            "viewer": 5
        },
        "peak_usage_hours": ["10:00", "14:00", "15:00"],
        "operations_per_user": [
            {"user": "john.doe", "operations": 345},
            {"user": "jane.smith", "operations": 278},
            {"user": "bob.wilson", "operations": 198}
        ]
    }
    
    return APIResponse(success=True, data=activity)

@router.get("/stats/trends")
async def get_trend_analysis(
    metric: str = "documents",
    days: int = 90,
    db: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user)
):
    """
    Get trend analysis for specified metric
    """
    trends = {
        "metric": metric,
        "period": f"last_{days}_days",
        "growth_rate": 12.5,  # percent
        "forecast_next_30d": 850,
        "seasonal_patterns": {
            "monday": 95,
            "tuesday": 120,
            "wednesday": 135,
            "thursday": 125,
            "friday": 110,
            "saturday": 45,
            "sunday": 35
        },
        "monthly_trend": [
            {"month": "Jan", "value": 450},
            {"month": "Feb", "value": 480},
            {"month": "Mar", "value": 520},
            {"month": "Apr", "value": 560},
            {"month": "May", "value": 610},
            {"month": "Jun", "value": 650}
        ]
    }
    
    return APIResponse(success=True, data=trends)

@router.get("/export-report")
async def export_dashboard_report(
    report_type: str = "summary",
    format: str = "json",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user)
):
    """
    Export dashboard report in various formats
    """
    report_data = {
        "generated_at": datetime.now().isoformat(),
        "report_type": report_type,
        "format": format,
        "period": {"start": start_date, "end": end_date},
        "generated_by": current_user["email"],
        "data": {
            "summary": {
                "total_documents": 1250,
                "fraud_detected": 45,
                "extraction_success_rate": 94.5
            }
        }
    }
    
    return APIResponse(
        success=True,
        message=f"Report exported successfully in {format} format",
        data=report_data
    )

@router.get("/recent-activity")
async def get_recent_activity(
    limit: int = 20,
    db: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user)
):
    """
    Get recent user activity feed
    """
    activities = [
        {
            "id": 1,
            "type": "document_uploaded",
            "user": "john.doe",
            "document_name": "invoice_2024_001.pdf",
            "timestamp": (datetime.now() - timedelta(minutes=5)).isoformat(),
            "status": "success"
        },
        {
            "id": 2,
            "type": "fraud_detected",
            "user": "system",
            "document_name": "suspicious_contract.pdf",
            "risk_score": 0.92,
            "timestamp": (datetime.now() - timedelta(hours=1)).isoformat(),
            "status": "alert"
        },
        {
            "id": 3,
            "type": "extraction_completed",
            "user": "jane.smith",
            "document_name": "form_application_123.pdf",
            "fields_extracted": 24,
            "timestamp": (datetime.now() - timedelta(hours=2)).isoformat(),
            "status": "success"
        }
    ]
    
    return APIResponse(success=True, data={"activities": activities[:limit]})