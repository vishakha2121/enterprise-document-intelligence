"""
Fraud Detection Routes
Detect fraud and anomalies in documents using AI
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
import logging

from app.dependencies import (
    get_db_session,
    get_fraud_service,
    get_current_user,
    check_rate_limit,
    get_cache_service
)
from app.services.fraud_service import FraudService
from app.services.cache_service import CacheService
from app.api.models.request_models import FraudCheckRequest, FraudReportRequest
from app.api.models.response_models import (
    FraudCheckResponse,
    FraudAlertResponse,
    FraudStatsResponse,
    APIResponse
)

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/check/{document_id}", response_model=APIResponse[FraudCheckResponse])
async def check_document_fraud(
    document_id: int,
    request: Optional[FraudCheckRequest] = None,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db_session),
    fraud_service: FraudService = Depends(get_fraud_service),
    cache_service: CacheService = Depends(get_cache_service),
    current_user: dict = Depends(get_current_user),
    rate_limit: None = Depends(check_rate_limit)
):
    """
    Perform comprehensive fraud detection on document
    
    Detection methods:
    - Rule-based validation
    - Anomaly detection
    - Duplicate detection
    - Signature verification
    - Keyword analysis
    - Pattern matching
    """
    # Check cache
    cache_key = f"fraud_check:{document_id}:{current_user['id']}"
    if cache_service:
        cached_result = await cache_service.get(cache_key)
        if cached_result:
            logger.info(f"Returning cached fraud check for document {document_id}")
            return APIResponse(
                success=True,
                data=FraudCheckResponse(**cached_result)
            )
    
    # Perform fraud detection
    try:
        fraud_result = await fraud_service.check_document_fraud(
            document_id=document_id,
            user_id=current_user["id"],
            check_types=request.check_types if request else None,
            threshold=request.threshold if request else 0.7
        )
        
        if not fraud_result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} not found"
            )
        
        # Cache result for high-risk documents only
        if cache_service and fraud_result.risk_score > 0.5:
            await cache_service.set(
                cache_key,
                fraud_result.dict(),
                ttl=3600  # Cache for 1 hour
            )
        
        # Create alert for high-risk documents
        if fraud_result.risk_score > 0.8:
            await fraud_service.create_fraud_alert(
                document_id=document_id,
                user_id=current_user["id"],
                fraud_result=fraud_result
            )
        
        message = "No fraud detected" if fraud_result.risk_score < 0.5 else f"⚠️ High risk detected! Risk score: {fraud_result.risk_score}"
        
        return APIResponse(
            success=True,
            message=message,
            data=fraud_result
        )
    
    except Exception as e:
        logger.error(f"Fraud check error for document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Fraud detection failed: {str(e)}"
        )

@router.post("/check-batch", response_model=APIResponse)
async def check_batch_fraud(
    document_ids: List[int],
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session),
    fraud_service: FraudService = Depends(get_fraud_service),
    current_user: dict = Depends(get_current_user)
):
    """
    Batch fraud detection for multiple documents
    """
    if len(document_ids) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 50 documents per batch fraud check"
        )
    
    task_id = await fraud_service.start_batch_fraud_check(
        document_ids=document_ids,
        user_id=current_user["id"],
        background_tasks=background_tasks
    )
    
    return APIResponse(
        success=True,
        message=f"Batch fraud check started for {len(document_ids)} documents",
        data={
            "task_id": task_id,
            "status_url": f"/api/v1/fraud/batch-status/{task_id}"
        }
    )

@router.get("/alerts", response_model=APIResponse[List[FraudAlertResponse]])
async def get_fraud_alerts(
    status: Optional[str] = None,
    severity: Optional[str] = None,
    limit: int = 50,
    db: AsyncSession = Depends(get_db_session),
    fraud_service: FraudService = Depends(get_fraud_service),
    current_user: dict = Depends(get_current_user)
):
    """
    Get fraud alerts for current user
    """
    alerts = await fraud_service.get_fraud_alerts(
        user_id=current_user["id"],
        status=status,
        severity=severity,
        limit=limit
    )
    
    return APIResponse(
        success=True,
        data=[FraudAlertResponse.from_orm(alert) for alert in alerts]
    )

@router.get("/alert/{alert_id}", response_model=APIResponse[FraudAlertResponse])
async def get_fraud_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db_session),
    fraud_service: FraudService = Depends(get_fraud_service),
    current_user: dict = Depends(get_current_user)
):
    """
    Get specific fraud alert by ID
    """
    alert = await fraud_service.get_fraud_alert(alert_id, current_user["id"])
    
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found"
        )
    
    return APIResponse(
        success=True,
        data=FraudAlertResponse.from_orm(alert)
    )

@router.put("/alert/{alert_id}/resolve")
async def resolve_fraud_alert(
    alert_id: int,
    resolution: Dict[str, Any],
    db: AsyncSession = Depends(get_db_session),
    fraud_service: FraudService = Depends(get_fraud_service),
    current_user: dict = Depends(get_current_user)
):
    """
    Resolve a fraud alert after investigation
    """
    result = await fraud_service.resolve_alert(
        alert_id=alert_id,
        user_id=current_user["id"],
        resolution_notes=resolution.get("notes"),
        is_fraud=resolution.get("is_fraud", True)
    )
    
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found"
        )
    
    return APIResponse(
        success=True,
        message="Alert resolved successfully",
        data={"resolved": True}
    )

@router.get("/stats", response_model=APIResponse[FraudStatsResponse])
async def get_fraud_statistics(
    days: int = 30,
    db: AsyncSession = Depends(get_db_session),
    fraud_service: FraudService = Depends(get_fraud_service),
    current_user: dict = Depends(get_current_user)
):
    """
    Get fraud detection statistics
    """
    stats = await fraud_service.get_fraud_statistics(
        user_id=current_user["id"],
        days=days
    )
    
    return APIResponse(
        success=True,
        data=FraudStatsResponse(
            total_checks=stats["total_checks"],
            fraud_detected=stats["fraud_detected"],
            suspicious_count=stats["suspicious_count"],
            clean_count=stats["clean_count"],
            high_risk_count=stats["high_risk_count"],
            medium_risk_count=stats["medium_risk_count"],
            low_risk_count=stats["low_risk_count"],
            average_risk_score=stats["avg_risk_score"],
            fraud_by_type=stats["fraud_by_type"],
            fraud_timeline=stats["timeline"],
            detection_rate=stats["detection_rate"]
        )
    )

@router.get("/rules")
async def get_fraud_detection_rules(
    fraud_service: FraudService = Depends(get_fraud_service)
):
    """
    Get all active fraud detection rules
    """
    rules = await fraud_service.get_detection_rules()
    
    return APIResponse(
        success=True,
        data={
            "rules": rules,
            "total_rules": len(rules),
            "rule_categories": ["amount_anomaly", "duplicate", "keyword", "pattern", "signature"]
        }
    )

@router.post("/rules")
async def add_fraud_detection_rule(
    rule: Dict[str, Any],
    fraud_service: FraudService = Depends(get_fraud_service),
    current_user: dict = Depends(get_current_user)
):
    """
    Add custom fraud detection rule
    """
    if current_user["role"] not in ["admin", "security"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to add rules"
        )
    
    new_rule = await fraud_service.add_detection_rule(rule)
    
    return APIResponse(
        success=True,
        message="Rule added successfully",
        data=new_rule
    )

@router.get("/report/{document_id}")
async def generate_fraud_report(
    document_id: int,
    format: str = "json",
    db: AsyncSession = Depends(get_db_session),
    fraud_service: FraudService = Depends(get_fraud_service),
    current_user: dict = Depends(get_current_user)
):
    """
    Generate detailed fraud analysis report
    """
    report = await fraud_service.generate_fraud_report(
        document_id=document_id,
        user_id=current_user["id"],
        format=format
    )
    
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document {document_id} not found"
        )
    
    return APIResponse(
        success=True,
        data=report
    )

@router.post("/validate-signature/{document_id}")
async def validate_document_signature(
    document_id: int,
    signature_data: Dict[str, Any],
    fraud_service: FraudService = Depends(get_fraud_service),
    current_user: dict = Depends(get_current_user)
):
    """
    Validate document signature (PDF digital signatures)
    """
    validation_result = await fraud_service.validate_signature(
        document_id=document_id,
        user_id=current_user["id"],
        signature_data=signature_data
    )
    
    return APIResponse(
        success=True,
        data=validation_result
    )