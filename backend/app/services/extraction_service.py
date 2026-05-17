"""
Extraction Service
Orchestrates document extraction using OCR and NLP
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.services.document_service import DocumentService
from app.services.cache_service import CacheService
from app.core.ocr.ocr_factory import OCRFactory, OCRProvider
from app.core.extraction.invoice_extractor import InvoiceExtractor
from app.core.extraction.contract_extractor import ContractExtractor
from app.core.extraction.form_extractor import FormExtractor
from app.core.extraction.field_mapper import FieldMapper, ERPSystem
from app.database.models.extraction import ExtractionResult
from app.config import settings

logger = logging.getLogger(__name__)

class ExtractionService:
    """Service for document data extraction"""
    
    def __init__(
        self,
        db: AsyncSession,
        ocr_factory: OCRFactory,
        cache_service: Optional[CacheService] = None
    ):
        self.db = db
        self.ocr_factory = ocr_factory
        self.cache = cache_service
        self.document_service = DocumentService(db, cache_service)
        
        # Initialize extractors
        self.invoice_extractor = InvoiceExtractor()
        self.contract_extractor = ContractExtractor()
        self.form_extractor = FormExtractor()
        self.field_mapper = FieldMapper()
    
    async def extract_document_data(
        self,
        document_id: int,
        user_id: int,
        fields: Optional[List[str]] = None,
        extraction_type: str = "full"
    ) -> Optional[Dict[str, Any]]:
        """Extract data from document"""
        # Get document
        document = await self.document_service.get_document(document_id, user_id)
        if not document:
            logger.error(f"Document {document_id} not found")
            return None
        
        try:
            # Update status to processing
            await self.document_service.update_document_status(document_id, "processing")
            
            # Get document file path
            file_path = await self.document_service.get_document_file(document)
            
            # Perform OCR
            ocr_result = await self.ocr_factory.extract_text(
                str(file_path),
                provider=OCRProvider.AUTO
            )
            
            if not ocr_result.get("success"):
                raise ValueError(f"OCR failed: {ocr_result.get('error', 'Unknown error')}")
            
            extracted_text = ocr_result.get("text", "")
            
            # Determine document type if not specified
            doc_type = document.document_type
            if not doc_type:
                # Auto-detect from content
                doc_type = await self._detect_document_type(extracted_text)
            
            # Extract based on document type
            extracted_data = await self._extract_by_type(
                extracted_text,
                doc_type,
                ocr_result
            )
            
            # Filter fields if specified
            if fields:
                extracted_data["extracted_data"] = {
                    k: v for k, v in extracted_data.get("extracted_data", {}).items()
                    if k in fields
                }
            
            # Save extraction result
            extraction_record = ExtractionResult(
                document_id=document_id,
                extraction_type=extraction_type,
                extracted_data=extracted_data.get("extracted_data", {}),
                confidence_score=extracted_data.get("overall_confidence", 0.0),
                processing_time_ms=ocr_result.get("processing_time_ms", 0),
                ocr_text=extracted_text if extraction_type == "full" else None,
                status="completed",
                created_at=datetime.now()
            )
            
            self.db.add(extraction_record)
            await self.db.commit()
            await self.db.refresh(extraction_record)
            
            # Update document status
            await self.document_service.update_document_status(document_id, "processed")
            
            # Cache result
            if self.cache:
                cache_key = f"extraction:{document_id}:{user_id}"
                await self.cache.set(cache_key, extraction_record.to_dict(), ttl=86400)
            
            logger.info(f"Extraction completed for document {document_id}")
            
            return extraction_record.to_dict()
        
        except Exception as e:
            logger.error(f"Extraction failed for document {document_id}: {str(e)}")
            await self.document_service.update_document_status(document_id, "failed", str(e))
            return None
    
    async def _detect_document_type(self, text: str) -> str:
        """Auto-detect document type from content"""
        text_lower = text.lower()
        
        # Simple keyword-based detection
        if any(word in text_lower for word in ["invoice", "bill", "purchase order", "amount due"]):
            return "invoice"
        elif any(word in text_lower for word in ["contract", "agreement", "terms and conditions", "parties"]):
            return "contract"
        elif any(word in text_lower for word in ["application", "form", "register", "submit"]):
            return "form"
        
        return "other"
    
    async def _extract_by_type(
        self,
        text: str,
        doc_type: str,
        ocr_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Extract data based on document type"""
        if doc_type == "invoice":
            return await self.invoice_extractor.extract(text)
        elif doc_type == "contract":
            return await self.contract_extractor.extract(text)
        elif doc_type == "form":
            return await self.form_extractor.extract(text)
        else:
            # Generic extraction
            return {
                "extracted_data": {"full_text": text[:5000]},
                "overall_confidence": 0.5
            }
    
    async def get_document_extractions(
        self,
        document_id: int,
        user_id: int
    ) -> List[ExtractionResult]:
        """Get all extraction results for a document"""
        stmt = select(ExtractionResult).where(
            ExtractionResult.document_id == document_id
        ).order_by(ExtractionResult.created_at.desc())
        
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def get_extraction_by_id(
        self,
        extraction_id: int,
        user_id: int
    ) -> Optional[ExtractionResult]:
        """Get extraction result by ID"""
        stmt = select(ExtractionResult).where(
            ExtractionResult.id == extraction_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def export_extraction_data(
        self,
        extraction_id: int,
        user_id: int,
        format: str = "json",
        include_metadata: bool = True,
        erp_system: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Export extraction data to specified format"""
        extraction = await self.get_extraction_by_id(extraction_id, user_id)
        if not extraction:
            return None
        
        data = extraction.extracted_data
        
        # Map to ERP format if requested
        if erp_system:
            doc_type = extraction.document.document_type if extraction.document else "other"
            erp_data = await self.field_mapper.map_to_erp(
                data,
                doc_type,
                ERPSystem(erp_system.lower())
            )
            data = erp_data
        
        export_data = {
            "data": data,
            "filename": f"extraction_{extraction_id}.{format}"
        }
        
        if include_metadata:
            export_data["metadata"] = {
                "extraction_id": extraction.id,
                "document_id": extraction.document_id,
                "extraction_type": extraction.extraction_type,
                "confidence_score": extraction.confidence_score,
                "created_at": extraction.created_at.isoformat()
            }
        
        return export_data
    
    async def start_batch_extraction(
        self,
        document_ids: List[int],
        user_id: int,
        background_tasks: Any
    ) -> str:
        """Start batch extraction for multiple documents"""
        task_id = f"batch_extract_{datetime.now().timestamp()}"
        
        # Add to background tasks
        background_tasks.add_task(
            self._process_batch_extraction,
            document_ids,
            user_id,
            task_id
        )
        
        return task_id
    
    async def _process_batch_extraction(
        self,
        document_ids: List[int],
        user_id: int,
        task_id: str
    ):
        """Process batch extraction in background"""
        results = []
        
        for doc_id in document_ids:
            try:
                result = await self.extract_document_data(doc_id, user_id)
                results.append({
                    "document_id": doc_id,
                    "success": result is not None,
                    "result": result
                })
            except Exception as e:
                results.append({
                    "document_id": doc_id,
                    "success": False,
                    "error": str(e)
                })
        
        # Store batch results in cache
        if self.cache:
            await self.cache.set(
                f"batch_extraction:{task_id}",
                {"results": results, "completed_at": datetime.now().isoformat()},
                ttl=3600
            )
    
    async def get_batch_status(self, task_id: str, user_id: int) -> Optional[Dict[str, Any]]:
        """Get batch extraction status"""
        if self.cache:
            return await self.cache.get(f"batch_extraction:{task_id}")
        return None
    
    async def validate_extraction(
        self,
        extraction_id: int,
        user_id: int,
        validation_data: Dict[str, Any]
    ) -> bool:
        """Validate and correct extraction results"""
        extraction = await self.get_extraction_by_id(extraction_id, user_id)
        if not extraction:
            return False
        
        # Update extraction with validation data
        extraction.validated_data = validation_data
        extraction.is_validated = True
        extraction.validated_at = datetime.now()
        extraction.validated_by = user_id
        
        await self.db.commit()
        
        # Clear cache
        if self.cache:
            await self.cache.delete(f"extraction:{extraction.document_id}:{user_id}")
        
        return True