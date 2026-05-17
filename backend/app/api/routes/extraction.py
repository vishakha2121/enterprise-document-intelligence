"""
Data Extraction Routes
Extract structured data from documents using AI
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status
from typing import Optional, Dict, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.dependencies import (
    get_db_session,
    get_extraction_service,
    get_current_user,
    check_rate_limit,
    get_cache_service
)
from app.services.extraction_service import ExtractionService
from app.services.cache_service import CacheService
from app.api.models.request_models import ExtractionRequest, ExportRequest
from app.api.models.response_models import (
    ExtractionResponse,
    ExtractionListResponse,
    APIResponse,
    ExportResponse
)

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/extract/{document_id}", response_model=APIResponse[ExtractionResponse])
async def extract_document_data(
    document_id: int,
    request: Optional[ExtractionRequest] = None,
    background_tasks: BackgroundTasks = None,
    db: AsyncSession = Depends(get_db_session),
    extraction_service: ExtractionService = Depends(get_extraction_service),
    cache_service: CacheService = Depends(get_cache_service),
    current_user: dict = Depends(get_current_user),
    rate_limit: None = Depends(check_rate_limit)
):
    """
    Extract structured data from document
    
    - **document_id**: ID of the document to extract data from
    - **fields**: Optional specific fields to extract (e.g., ["amount", "date", "invoice_number"])
    - **extraction_type**: Type of extraction (full, specific_fields, custom)
    """
    # Check cache first
    cache_key = f"extraction:{document_id}:{current_user['id']}"
    if cache_service:
        cached_data = await cache_service.get(cache_key)
        if cached_data:
            logger.info(f"Returning cached extraction for document {document_id}")
            return APIResponse(
                success=True,
                message="Extraction completed (from cache)",
                data=ExtractionResponse(**cached_data)
            )
    
    # Perform extraction
    try:
        extraction_result = await extraction_service.extract_document_data(
            document_id=document_id,
            user_id=current_user["id"],
            fields=request.fields if request else None,
            extraction_type=request.extraction_type if request else "full"
        )
        
        if not extraction_result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document {document_id} not found or extraction failed"
            )
        
        # Cache results
        if cache_service and extraction_result:
            await cache_service.set(
                cache_key,
                extraction_result.dict(),
                ttl=3600  # Cache for 1 hour
            )
        
        return APIResponse(
            success=True,
            message="Data extraction completed successfully",
            data=extraction_result
        )
    
    except Exception as e:
        logger.error(f"Extraction error for document {document_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Extraction failed: {str(e)}"
        )

@router.get("/extractions/{document_id}", response_model=APIResponse[List[ExtractionResponse]])
async def get_document_extractions(
    document_id: int,
    db: AsyncSession = Depends(get_db_session),
    extraction_service: ExtractionService = Depends(get_extraction_service),
    current_user: dict = Depends(get_current_user)
):
    """
    Get all extraction results for a document
    """
    extractions = await extraction_service.get_document_extractions(
        document_id=document_id,
        user_id=current_user["id"]
    )
    
    return APIResponse(
        success=True,
        data=[ExtractionResponse.from_orm(ext) for ext in extractions]
    )

@router.get("/extraction/{extraction_id}", response_model=APIResponse[ExtractionResponse])
async def get_extraction_by_id(
    extraction_id: int,
    db: AsyncSession = Depends(get_db_session),
    extraction_service: ExtractionService = Depends(get_extraction_service),
    current_user: dict = Depends(get_current_user)
):
    """
    Get extraction result by ID
    """
    extraction = await extraction_service.get_extraction_by_id(
        extraction_id=extraction_id,
        user_id=current_user["id"]
    )
    
    if not extraction:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Extraction with ID {extraction_id} not found"
        )
    
    return APIResponse(
        success=True,
        data=ExtractionResponse.from_orm(extraction)
    )

@router.post("/export/{extraction_id}", response_model=APIResponse[ExportResponse])
async def export_extraction_data(
    extraction_id: int,
    export_request: ExportRequest,
    db: AsyncSession = Depends(get_db_session),
    extraction_service: ExtractionService = Depends(get_extraction_service),
    current_user: dict = Depends(get_current_user)
):
    """
    Export extraction data to various formats
    
    - **format**: Export format (json, csv, xml, erp_ready)
    - **include_metadata**: Include document metadata in export
    - **erp_system**: ERP system format (if format="erp_ready")
    """
    export_data = await extraction_service.export_extraction_data(
        extraction_id=extraction_id,
        user_id=current_user["id"],
        format=export_request.format,
        include_metadata=export_request.include_metadata,
        erp_system=export_request.erp_system
    )
    
    if not export_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Extraction {extraction_id} not found"
        )
    
    return APIResponse(
        success=True,
        message=f"Data exported successfully in {export_request.format} format",
        data=ExportResponse(
            format=export_request.format,
            data=export_data["data"],
            filename=export_data["filename"],
            download_url=f"/api/v1/extraction/download/{export_data['file_id']}"
        )
    )

@router.post("/batch-extract")
async def batch_extract_documents(
    document_ids: List[int],
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session),
    extraction_service: ExtractionService = Depends(get_extraction_service),
    current_user: dict = Depends(get_current_user)
):
    """
    Batch extraction for multiple documents
    """
    if len(document_ids) > 50:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 50 documents per batch extraction"
        )
    
    task_id = await extraction_service.start_batch_extraction(
        document_ids=document_ids,
        user_id=current_user["id"],
        background_tasks=background_tasks
    )
    
    return APIResponse(
        success=True,
        message=f"Batch extraction started for {len(document_ids)} documents",
        data={
            "task_id": task_id,
            "total_documents": len(document_ids),
            "status_url": f"/api/v1/extraction/batch-status/{task_id}"
        }
    )

@router.get("/batch-status/{task_id}")
async def get_batch_extraction_status(
    task_id: str,
    extraction_service: ExtractionService = Depends(get_extraction_service),
    current_user: dict = Depends(get_current_user)
):
    """
    Get status of batch extraction task
    """
    status = await extraction_service.get_batch_status(task_id, current_user["id"])
    
    if not status:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task {task_id} not found"
        )
    
    return APIResponse(
        success=True,
        data=status
    )

@router.get("/fields/supported")
async def get_supported_extraction_fields(
    document_type: Optional[str] = None
):
    """
    Get list of supported extraction fields
    """
    supported_fields = {
        "invoice": [
            "invoice_number", "invoice_date", "due_date",
            "vendor_name", "vendor_address", "vendor_gst",
            "customer_name", "customer_address", "customer_gst",
            "subtotal", "tax_amount", "total_amount",
            "currency", "payment_terms", "line_items"
        ],
        "contract": [
            "contract_id", "contract_date", "effective_date",
            "expiry_date", "parties_involved", "contract_value",
            "terms_conditions", "signatures", "witnesses"
        ],
        "form": [
            "form_id", "submission_date", "applicant_name",
            "applicant_details", "purpose", "declarations"
        ],
        "common": [
            "document_title", "document_date", "author",
            "organization", "confidence_score"
        ]
    }
    
    if document_type and document_type in supported_fields:
        fields = supported_fields[document_type] + supported_fields["common"]
    else:
        fields = supported_fields
    
    return APIResponse(
        success=True,
        data={
            "document_types": list(supported_fields.keys()),
            "fields_by_type": supported_fields,
            "suggested_fields": fields
        }
    )

@router.post("/validate-extraction/{extraction_id}")
async def validate_extraction_accuracy(
    extraction_id: int,
    validation_data: Dict[str, Any],
    db: AsyncSession = Depends(get_db_session),
    extraction_service: ExtractionService = Depends(get_extraction_service),
    current_user: dict = Depends(get_current_user)
):
    """
    Validate and correct extraction results (feedback loop)
    """
    result = await extraction_service.validate_extraction(
        extraction_id=extraction_id,
        user_id=current_user["id"],
        validation_data=validation_data
    )
    
    return APIResponse(
        success=True,
        message="Extraction validation submitted",
        data={"accuracy_improved": result}
    )