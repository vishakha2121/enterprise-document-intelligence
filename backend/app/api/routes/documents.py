"""
Document Management Routes
Upload, download, list, and manage documents
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from fastapi.responses import FileResponse, StreamingResponse
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import uuid
from datetime import datetime
import logging

from app.dependencies import (
    get_db_session,
    get_document_service,
    get_current_user,
    check_rate_limit,
    validate_file_size,
    get_allowed_extensions,
    get_pagination_params,
    PaginationParams
)
from app.services.document_service import DocumentService
from app.api.models.request_models import DocumentUploadRequest, DocumentUpdateRequest
from app.api.models.response_models import (
    DocumentResponse,
    DocumentListResponse,
    UploadResponse,
    APIResponse
)
from app.utils.file_validator import validate_file, FileValidationError

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/upload", response_model=APIResponse[UploadResponse])
async def upload_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    document_type: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db_session),
    document_service: DocumentService = Depends(get_document_service),
    current_user: dict = Depends(get_current_user),
    rate_limit: None = Depends(check_rate_limit)
):
    """
    Upload a document for processing
    
    - **file**: Document file (PDF, JPG, PNG, TIFF)
    - **title**: Optional title for the document
    - **description**: Optional description
    - **document_type**: Optional document type hint
    
    Supported formats: PDF, JPEG, PNG, TIFF
    Max file size: 10MB
    """
    try:
        # Validate file
        is_valid, error_message = validate_file(
            file.filename,
            file.size if hasattr(file, 'size') else None,
            get_allowed_extensions()
        )
        
        if not is_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_message
            )
        
        # Validate file size
        if hasattr(file, 'size'):
            await validate_file_size(file.size)
        
        # Upload document
        document = await document_service.upload_document(
            file=file,
            user_id=current_user["id"],
            title=title,
            description=description,
            document_type=document_type
        )
        
        return APIResponse(
            success=True,
            message="Document uploaded successfully",
            data=UploadResponse(
                document_id=document.id,
                filename=document.filename,
                status=document.status,
                upload_url=f"/api/v1/documents/{document.id}"
            )
        )
    
    except FileValidationError as e:
        logger.error(f"File validation error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Document upload error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload document: {str(e)}"
        )

@router.post("/upload-batch", response_model=APIResponse[List[UploadResponse]])
async def upload_batch_documents(
    files: List[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db_session),
    document_service: DocumentService = Depends(get_document_service),
    current_user: dict = Depends(get_current_user),
    rate_limit: None = Depends(check_rate_limit)
):
    """
    Upload multiple documents in batch
    
    - **files**: List of document files (max 10 files per batch)
    """
    if len(files) > 10:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum 10 files per batch upload"
        )
    
    results = []
    errors = []
    
    for file in files:
        try:
            # Validate file
            is_valid, error_message = validate_file(
                file.filename,
                get_allowed_extensions()
            )
            
            if not is_valid:
                errors.append({"filename": file.filename, "error": error_message})
                continue
            
            # Upload document
            document = await document_service.upload_document(
                file=file,
                user_id=current_user["id"]
            )
            
            results.append(UploadResponse(
                document_id=document.id,
                filename=document.filename,
                status=document.status
            ))
        
        except Exception as e:
            errors.append({"filename": file.filename, "error": str(e)})
    
    return APIResponse(
        success=True,
        message=f"Uploaded {len(results)} documents successfully. {len(errors)} failed.",
        data=results,
        errors=errors if errors else None
    )

@router.get("/{document_id}", response_model=APIResponse[DocumentResponse])
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db_session),
    document_service: DocumentService = Depends(get_document_service),
    current_user: dict = Depends(get_current_user)
):
    """
    Get document details by ID
    """
    document = await document_service.get_document(document_id, current_user["id"])
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found"
        )
    
    return APIResponse(
        success=True,
        data=DocumentResponse.from_orm(document)
    )

@router.get("/{document_id}/download")
async def download_document(
    document_id: int,
    document_service: DocumentService = Depends(get_document_service),
    current_user: dict = Depends(get_current_user)
):
    """
    Download document file
    """
    document = await document_service.get_document(document_id, current_user["id"])
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found"
        )
    
    file_path = await document_service.get_document_file(document)
    
    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found"
        )
    
    return FileResponse(
        path=file_path,
        filename=document.filename,
        media_type="application/octet-stream"
    )

@router.get("/{document_id}/preview")
async def preview_document(
    document_id: int,
    document_service: DocumentService = Depends(get_document_service),
    current_user: dict = Depends(get_current_user)
):
    """
    Get document preview (first page as image)
    """
    preview = await document_service.get_document_preview(document_id, current_user["id"])
    
    if not preview:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Preview not available for this document"
        )
    
    return StreamingResponse(
        preview,
        media_type="image/jpeg",
        headers={"Content-Disposition": f"inline; filename=preview_{document_id}.jpg"}
    )

@router.get("/", response_model=APIResponse[DocumentListResponse])
async def list_documents(
    pagination: PaginationParams = Depends(get_pagination_params),
    document_type: Optional[str] = None,
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session),
    document_service: DocumentService = Depends(get_document_service),
    current_user: dict = Depends(get_current_user)
):
    """
    List all documents for current user with pagination and filters
    
    - **document_type**: Filter by document type (invoice, contract, form)
    - **status**: Filter by processing status
    - **search**: Search in filename and title
    """
    documents, total = await document_service.list_documents(
        user_id=current_user["id"],
        document_type=document_type,
        status=status,
        search=search,
        offset=pagination.offset,
        limit=pagination.limit,
        sort_by=pagination.sort_by,
        sort_order=pagination.sort_order
    )
    
    return APIResponse(
        success=True,
        data=DocumentListResponse(
            items=[DocumentResponse.from_orm(doc) for doc in documents],
            total=total,
            page=pagination.page,
            page_size=pagination.limit,
            total_pages=(total + pagination.limit - 1) // pagination.limit
        )
    )

@router.put("/{document_id}", response_model=APIResponse[DocumentResponse])
async def update_document(
    document_id: int,
    update_data: DocumentUpdateRequest,
    db: AsyncSession = Depends(get_db_session),
    document_service: DocumentService = Depends(get_document_service),
    current_user: dict = Depends(get_current_user)
):
    """
    Update document metadata
    """
    document = await document_service.update_document(
        document_id=document_id,
        user_id=current_user["id"],
        **update_data.dict(exclude_unset=True)
    )
    
    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found"
        )
    
    return APIResponse(
        success=True,
        message="Document updated successfully",
        data=DocumentResponse.from_orm(document)
    )

@router.delete("/{document_id}", response_model=APIResponse)
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_db_session),
    document_service: DocumentService = Depends(get_document_service),
    current_user: dict = Depends(get_current_user)
):
    """
    Delete document permanently
    """
    deleted = await document_service.delete_document(document_id, current_user["id"])
    
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found"
        )
    
    return APIResponse(
        success=True,
        message="Document deleted successfully"
    )

@router.post("/{document_id}/reprocess", response_model=APIResponse)
async def reprocess_document(
    document_id: int,
    db: AsyncSession = Depends(get_db_session),
    document_service: DocumentService = Depends(get_document_service),
    current_user: dict = Depends(get_current_user)
):
    """
    Reprocess document (re-run OCR and extraction)
    """
    task_id = await document_service.reprocess_document(document_id, current_user["id"])
    
    return APIResponse(
        success=True,
        message="Document reprocessing started",
        data={"task_id": task_id}
    )

@router.get("/stats/summary", response_model=APIResponse)
async def get_document_stats(
    db: AsyncSession = Depends(get_db_session),
    document_service: DocumentService = Depends(get_document_service),
    current_user: dict = Depends(get_current_user)
):
    """
    Get document statistics for current user
    """
    stats = await document_service.get_user_stats(current_user["id"])
    
    return APIResponse(
        success=True,
        data=stats
    )