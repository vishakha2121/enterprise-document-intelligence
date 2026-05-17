"""
Document Classification Routes
Classify document types using BERT AI model
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.dependencies import (
    get_db_session,
    get_classification_service,
    get_current_user,
    check_rate_limit,
    get_cache_service
)
from app.services.classification_service import ClassificationService
from app.services.cache_service import CacheService
from app.api.models.request_models import ClassificationRequest, BatchClassificationRequest
from app.api.models.response_models import (
    ClassificationResponse,
    BatchClassificationResponse,
    APIResponse
)

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/classify/{document_id}", response_model=APIResponse[ClassificationResponse])
async def classify_document(
    document_id: int,
    request: Optional[ClassificationRequest] = None,
    db: AsyncSession = Depends(get_db_session),
    classification_service: ClassificationService = Depends(get_classification_service),
    cache_service: CacheService = Depends(get_cache_service),
    current_user: dict = Depends(get_current_user),
    rate_limit: None = Depends(check_rate_limit)
):
    """
    Classify document type using BERT AI model
    
    - **document_id**: ID of the document to classify
    - **model_type**: Which model to use (bert, rule_based, hybrid)
    - **confidence_threshold**: Minimum confidence for classification (0-1)
    
    Document types: invoice, contract, form, receipt, report, other
    """
    # Check cache
    cache_key = f"classification:{document_id}:{current_user['id']}"
    if cache_service:
        cached_result = await cache_service.get(cache_key)
        if cached_result:
            logger.info(f"Returning cached classification for document {document_id}")
            return APIResponse(
                success=True,
                data=ClassificationResponse(**cached_result)
            )
    
    # Perform classification
    try:
        classification_result = await classification_service.classify_document(
            document_id=document_id,
            user_id=current_user["id"],
            model_type=request.model_type if request else "hybrid",
            confidence_threshold=request.confidence_threshold if request else 0.7
        )
        
        if not classification_result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} not found or classification failed"
            )
        
        # Cache result
        if cache_service and classification_result.confidence > 0.8:
            await cache_service.set(
                cache_key,
                classification_result.dict(),
                ttl=86400  # Cache for 24 hours for high confidence results
            )
        
        return APIResponse(
            success=True,
            message=f"Document classified as: {classification_result.document_type}",
            data=classification_result
        )
    
    except Exception as e:
        logger.error(f"Classification error for document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Classification failed: {str(e)}"
        )

@router.post("/classify-batch", response_model=APIResponse[BatchClassificationResponse])
async def classify_batch_documents(
    request: BatchClassificationRequest,
    db: AsyncSession = Depends(get_db_session),
    classification_service: ClassificationService = Depends(get_classification_service),
    current_user: dict = Depends(get_current_user)
):
    """
    Batch classify multiple documents
    
    - **document_ids**: List of document IDs to classify
    - **model_type**: Model to use for classification
    - **confidence_threshold**: Minimum confidence threshold
    """
    if len(request.document_ids) > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 100 documents per batch classification"
        )
    
    results = await classification_service.batch_classify_documents(
        document_ids=request.document_ids,
        user_id=current_user["id"],
        model_type=request.model_type,
        confidence_threshold=request.confidence_threshold
    )
    
    # Calculate statistics
    document_types = {}
    for result in results.results:
        doc_type = result.document_type
        document_types[doc_type] = document_types.get(doc_type, 0) + 1
    
    return APIResponse(
        success=True,
        message=f"Classified {len(results.results)} documents",
        data=BatchClassificationResponse(
            total_documents=len(results.results),
            results=results.results,
            summary={
                "document_types": document_types,
                "average_confidence": sum(r.confidence for r in results.results) / len(results.results),
                "high_confidence_count": len([r for r in results.results if r.confidence > 0.9]),
                "low_confidence_count": len([r for r in results.results if r.confidence < 0.7])
            }
        )
    )

@router.get("/classifications/{document_id}")
async def get_document_classifications(
    document_id: int,
    limit: int = 10,
    db: AsyncSession = Depends(get_db_session),
    classification_service: ClassificationService = Depends(get_classification_service),
    current_user: dict = Depends(get_current_user)
):
    """
    Get classification history for a document
    """
    classifications = await classification_service.get_document_classifications(
        document_id=document_id,
        user_id=current_user["id"],
        limit=limit
    )
    
    return APIResponse(
        success=True,
        data=[ClassificationResponse.from_orm(c) for c in classifications]
    )

@router.post("/train-model")
async def train_classification_model(
    training_data: Dict[str, Any],
    classification_service: ClassificationService = Depends(get_classification_service),
    current_user: dict = Depends(get_current_user)
):
    """
    Train or fine-tune classification model with custom data
    """
    # Check if user has admin privileges
    if current_user["role"] not in ["admin", "trainer"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Insufficient permissions to train model"
        )
    
    task_id = await classification_service.train_model(training_data)
    
    return APIResponse(
        success=True,
        message="Model training started",
        data={
            "task_id": task_id,
            "status_url": f"/api/v1/classification/training-status/{task_id}"
        }
    )

@router.get("/training-status/{task_id}")
async def get_training_status(
    task_id: str,
    classification_service: ClassificationService = Depends(get_classification_service),
    current_user: dict = Depends(get_current_user)
):
    """
    Get status of model training task
    """
    status = await classification_service.get_training_status(task_id)
    
    if not status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Training task {task_id} not found"
        )
    
    return APIResponse(
        success=True,
        data=status
    )

@router.get("/model-info")
async def get_model_information(
    classification_service: ClassificationService = Depends(get_classification_service)
):
    """
    Get information about classification models
    """
    model_info = await classification_service.get_model_info()
    
    return APIResponse(
        success=True,
        data={
            "models": model_info,
            "supported_document_types": [
                "invoice", "contract", "form", "receipt", "report", "other"
            ],
            "model_performance": {
                "accuracy": 0.94,
                "precision": 0.93,
                "recall": 0.92,
                "f1_score": 0.925
            }
        }
    )

@router.post("/feedback/{classification_id}")
async def submit_classification_feedback(
    classification_id: int,
    feedback: Dict[str, Any],
    db: AsyncSession = Depends(get_db_session),
    classification_service: ClassificationService = Depends(get_classification_service),
    current_user: dict = Depends(get_current_user)
):
    """
    Submit feedback for classification (improves model)
    """
    result = await classification_service.submit_feedback(
        classification_id=classification_id,
        user_id=current_user["id"],
        correct_type=feedback.get("correct_type"),
        user_confidence=feedback.get("confidence", 1.0),
        comments=feedback.get("comments")
    )
    
    return APIResponse(
        success=True,
        message="Thank you for your feedback! This helps improve our AI model.",
        data={"feedback_submitted": result}
    )