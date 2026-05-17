"""
Document Service
Handles document upload, storage, retrieval, and management
"""

import uuid
import shutil
from pathlib import Path
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
import logging
from fastapi import UploadFile

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, or_, and_
from sqlalchemy.orm import selectinload

from app.database.models.document import Document
from app.database.models.user import User
from app.services.cache_service import CacheService
from app.utils.file_validator import FileValidator
from app.config import settings

logger = logging.getLogger(__name__)

class DocumentService:
    """Service for document management operations"""
    
    def __init__(self, db: AsyncSession, cache_service: Optional[CacheService] = None):
        self.db = db
        self.cache = cache_service
        self.file_validator = FileValidator()
    
    async def upload_document(
        self,
        file: UploadFile,
        user_id: int,
        title: Optional[str] = None,
        description: Optional[str] = None,
        document_type: Optional[str] = None,
        tags: Optional[List[str]] = None
    ) -> Document:
        """Upload and store a document"""
        try:
            # Validate file
            validation_result = self.file_validator.validate(file.filename, file.size if hasattr(file, 'size') else None)
            if not validation_result["is_valid"]:
                raise ValueError(validation_result["error"])
            
            # Generate unique filename
            file_ext = Path(file.filename).suffix
            unique_filename = f"{uuid.uuid4().hex}{file_ext}"
            
            # Save file to disk
            file_path = settings.UPLOAD_DIR / unique_filename
            content = await file.read()
            
            with open(file_path, "wb") as f:
                f.write(content)
            
            # Create document record
            document = Document(
                filename=file.filename,
                file_path=str(file_path),
                file_size=len(content),
                file_type=file.content_type or "application/octet-stream",
                title=title or file.filename,
                description=description,
                document_type=document_type,
                user_id=user_id,
                tags=tags or [],
                status="uploaded",
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            
            self.db.add(document)
            await self.db.commit()
            await self.db.refresh(document)
            
            # Clear cache
            if self.cache:
                await self.cache.delete_pattern(f"user_documents:{user_id}:*")
            
            logger.info(f"Document uploaded: {document.id} - {document.filename}")
            return document
        
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Document upload failed: {str(e)}")
            raise
    
    async def get_document(self, document_id: int, user_id: int) -> Optional[Document]:
        """Get document by ID"""
        # Check cache
        if self.cache:
            cache_key = f"document:{document_id}:user:{user_id}"
            cached = await self.cache.get(cache_key)
            if cached:
                return Document(**cached)
        
        # Query database
        stmt = select(Document).where(
            and_(
                Document.id == document_id,
                Document.user_id == user_id,
                Document.is_deleted == False
            )
        )
        result = await self.db.execute(stmt)
        document = result.scalar_one_or_none()
        
        # Cache result
        if document and self.cache:
            await self.cache.set(cache_key, document.to_dict(), ttl=3600)
        
        return document
    
    async def list_documents(
        self,
        user_id: int,
        document_type: Optional[str] = None,
        status: Optional[str] = None,
        search: Optional[str] = None,
        offset: int = 0,
        limit: int = 20,
        sort_by: Optional[str] = "created_at",
        sort_order: str = "desc"
    ) -> Tuple[List[Document], int]:
        """List documents with pagination and filters"""
        # Build query
        stmt = select(Document).where(
            and_(
                Document.user_id == user_id,
                Document.is_deleted == False
            )
        )
        
        # Apply filters
        if document_type:
            stmt = stmt.where(Document.document_type == document_type)
        
        if status:
            stmt = stmt.where(Document.status == status)
        
        if search:
            stmt = stmt.where(
                or_(
                    Document.filename.ilike(f"%{search}%"),
                    Document.title.ilike(f"%{search}%"),
                    Document.description.ilike(f"%{search}%")
                )
            )
        
        # Get total count
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total_result = await self.db.execute(count_stmt)
        total = total_result.scalar()
        
        # Apply sorting
        if sort_by and hasattr(Document, sort_by):
            sort_column = getattr(Document, sort_by)
            if sort_order == "desc":
                stmt = stmt.order_by(sort_column.desc())
            else:
                stmt = stmt.order_by(sort_column.asc())
        
        # Apply pagination
        stmt = stmt.offset(offset).limit(limit)
        
        # Execute query
        result = await self.db.execute(stmt)
        documents = result.scalars().all()
        
        return documents, total
    
    async def update_document(
        self,
        document_id: int,
        user_id: int,
        **kwargs
    ) -> Optional[Document]:
        """Update document metadata"""
        document = await self.get_document(document_id, user_id)
        if not document:
            return None
        
        # Update fields
        allowed_fields = ["title", "description", "document_type", "tags", "status"]
        for field, value in kwargs.items():
            if field in allowed_fields and value is not None:
                setattr(document, field, value)
        
        document.updated_at = datetime.now()
        
        await self.db.commit()
        await self.db.refresh(document)
        
        # Clear cache
        if self.cache:
            await self.cache.delete(f"document:{document_id}:user:{user_id}")
        
        return document
    
    async def delete_document(self, document_id: int, user_id: int) -> bool:
        """Soft delete a document"""
        document = await self.get_document(document_id, user_id)
        if not document:
            return False
        
        document.is_deleted = True
        document.deleted_at = datetime.now()
        document.status = "deleted"
        
        await self.db.commit()
        
        # Clear cache
        if self.cache:
            await self.cache.delete(f"document:{document_id}:user:{user_id}")
        
        # Delete file from disk (optional - can keep for recovery)
        file_path = Path(document.file_path)
        if file_path.exists():
            # Move to trash instead of delete
            trash_path = settings.UPLOAD_DIR / "trash" / file_path.name
            trash_path.parent.mkdir(exist_ok=True)
            shutil.move(str(file_path), str(trash_path))
        
        logger.info(f"Document deleted: {document_id}")
        return True
    
    async def get_document_file(self, document: Document) -> Path:
        """Get document file path"""
        file_path = Path(document.file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"Document file not found: {document.file_path}")
        return file_path
    
    async def get_document_preview(self, document_id: int, user_id: int) -> Optional[bytes]:
        """Get document preview (first page as image)"""
        document = await self.get_document(document_id, user_id)
        if not document:
            return None
        
        # For PDF, generate preview
        if document.file_type == "application/pdf":
            try:
                from pdf2image import convert_from_path
                images = convert_from_path(document.file_path, first_page=1, last_page=1)
                if images:
                    import io
                    img_byte_arr = io.BytesIO()
                    images[0].save(img_byte_arr, format='JPEG', quality=85)
                    return img_byte_arr.getvalue()
            except Exception as e:
                logger.error(f"PDF preview failed: {str(e)}")
        
        # For images, return the image itself
        elif document.file_type.startswith("image/"):
            with open(document.file_path, "rb") as f:
                return f.read()
        
        return None
    
    async def update_document_status(
        self,
        document_id: int,
        status: str,
        error_message: Optional[str] = None
    ) -> Optional[Document]:
        """Update document processing status"""
        document = await self.get_document(document_id, document.user_id if document else None)
        if not document:
            return None
        
        document.status = status
        if status == "processed":
            document.processed_at = datetime.now()
        if error_message:
            document.error_message = error_message
        
        document.updated_at = datetime.now()
        
        await self.db.commit()
        await self.db.refresh(document)
        
        return document
    
    async def get_user_stats(self, user_id: int) -> Dict[str, Any]:
        """Get document statistics for user"""
        # Total documents
        total_stmt = select(func.count()).where(
            and_(
                Document.user_id == user_id,
                Document.is_deleted == False
            )
        )
        total_result = await self.db.execute(total_stmt)
        total_documents = total_result.scalar()
        
        # Documents by type
        type_stmt = select(
            Document.document_type,
            func.count()
        ).where(
            and_(
                Document.user_id == user_id,
                Document.is_deleted == False,
                Document.document_type.isnot(None)
            )
        ).group_by(Document.document_type)
        
        type_result = await self.db.execute(type_stmt)
        documents_by_type = dict(type_result.all())
        
        # Documents by status
        status_stmt = select(
            Document.status,
            func.count()
        ).where(
            and_(
                Document.user_id == user_id,
                Document.is_deleted == False
            )
        ).group_by(Document.status)
        
        status_result = await self.db.execute(status_stmt)
        documents_by_status = dict(status_result.all())
        
        # Total file size
        size_stmt = select(func.sum(Document.file_size)).where(
            and_(
                Document.user_id == user_id,
                Document.is_deleted == False
            )
        )
        size_result = await self.db.execute(size_stmt)
        total_size = size_result.scalar() or 0
        
        return {
            "total_documents": total_documents,
            "documents_by_type": documents_by_type,
            "documents_by_status": documents_by_status,
            "total_storage_mb": round(total_size / (1024 * 1024), 2)
        }
    
    async def search_documents(self, query: str, user_id: int, limit: int = 20) -> List[Document]:
        """Search documents by content and metadata"""
        stmt = select(Document).where(
            and_(
                Document.user_id == user_id,
                Document.is_deleted == False,
                or_(
                    Document.title.ilike(f"%{query}%"),
                    Document.filename.ilike(f"%{query}%"),
                    Document.description.ilike(f"%{query}%"),
                    Document.tags.any(query)
                )
            )
        ).limit(limit)
        
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def reprocess_document(self, document_id: int, user_id: int) -> str:
        """Mark document for reprocessing"""
        document = await self.get_document(document_id, user_id)
        if not document:
            raise ValueError(f"Document {document_id} not found")
        
        # Reset status
        document.status = "pending"
        document.processed_at = None
        document.error_message = None
        
        await self.db.commit()
        
        # Clear extraction cache
        if self.cache:
            await self.cache.delete(f"extraction:{document_id}:{user_id}")
        
        # Return task ID for async processing
        task_id = f"reprocess_{document_id}_{datetime.now().timestamp()}"
        return task_id