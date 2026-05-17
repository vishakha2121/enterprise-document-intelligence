"""
Document Processing Tasks
Async tasks for document processing with Celery
"""

import asyncio
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime
from pathlib import Path

from celery import shared_task
from celery.exceptions import Retry

from app.workers.celery_app import celery_app
from app.config import settings
from app.database.session import async_session_maker
from app.services.document_service import DocumentService
from app.services.extraction_service import ExtractionService
from app.services.classification_service import ClassificationService
from app.services.fraud_service import FraudService
from app.services.cache_service import CacheService
from app.core.ocr.ocr_factory import OCRFactory, StorageType
from app.core.nlp.model_loader import ModelLoader
from app.utils.helpers import retry_async
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Global instances (initialized once per worker)
_ocr_factory = None
_model_loader = None
_cache_service = None

def get_ocr_factory():
    """Get or create OCR factory instance"""
    global _ocr_factory
    if _ocr_factory is None:
        _ocr_factory = OCRFactory()
    return _ocr_factory

def get_model_loader():
    """Get or create model loader instance"""
    global _model_loader
    if _model_loader is None:
        _model_loader = ModelLoader()
    return _model_loader

def get_cache_service():
    """Get or create cache service"""
    global _cache_service
    if _cache_service is None:
        from app.dependencies import get_redis_client
        redis_client = get_redis_client()
        if redis_client:
            _cache_service = CacheService(redis_client)
    return _cache_service

@shared_task(name="app.workers.document_tasks.process_document_task", bind=True, max_retries=3)
def process_document_task(self, document_id: int, user_id: int):
    """
    Process document: OCR -> Classification -> Extraction -> Fraud Detection
    
    Args:
        document_id: Document ID to process
        user_id: User ID who owns the document
    """
    logger.info(f"Starting document processing task: document_id={document_id}, user_id={user_id}")
    
    try:
        # Run async processing in event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            result = loop.run_until_complete(
                _process_document_async(document_id, user_id)
            )
            return result
        finally:
            loop.close()
            
    except Exception as e:
        logger.error(f"Document processing failed: {str(e)}", exc_info=True)
        
        # Retry on certain exceptions
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))
        
        # Update document status to failed
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(
                _mark_document_failed(document_id, user_id, str(e))
            )
        finally:
            loop.close()
        
        raise

async def _process_document_async(document_id: int, user_id: int) -> Dict[str, Any]:
    """Async implementation of document processing"""
    async with async_session_maker() as db:
        document_service = DocumentService(db, get_cache_service())
        extraction_service = ExtractionService(
            db, 
            get_ocr_factory(),
            get_cache_service()
        )
        classification_service = ClassificationService(
            get_model_loader(),
            get_cache_service()
        )
        fraud_service = FraudService(db, get_cache_service())
        
        # Get document
        document = await document_service.get_document(document_id, user_id)
        if not document:
            raise ValueError(f"Document {document_id} not found")
        
        # Update status
        await document_service.update_document_status(document_id, "processing")
        
        # Step 1: Extract data (includes OCR)
        extraction_result = await extraction_service.extract_document_data(
            document_id, user_id
        )
        
        if not extraction_result:
            raise ValueError("Extraction failed")
        
        # Step 2: Classify document
        classification_result = await classification_service.classify_document(
            document_id, user_id
        )
        
        # Step 3: Fraud detection
        fraud_result = await fraud_service.check_document_fraud(
            document_id, user_id
        )
        
        # Update document with classification
        if classification_result:
            await document_service.update_document(
                document_id, user_id,
                document_type=classification_result.get("document_type"),
                classification_confidence=classification_result.get("confidence")
            )
        
        # Update status to completed
        await document_service.update_document_status(document_id, "processed")
        
        # Cache results
        cache = get_cache_service()
        if cache:
            await cache.set(
                f"doc_{document_id}_extraction",
                extraction_result,
                ttl=3600
            )
        
        return {
            "success": True,
            "document_id": document_id,
            "extraction": extraction_result,
            "classification": classification_result,
            "fraud": fraud_result
        }

async def _mark_document_failed(document_id: int, user_id: int, error: str):
    """Mark document as failed"""
    async with async_session_maker() as db:
        document_service = DocumentService(db, get_cache_service())
        await document_service.update_document_status(document_id, "failed", error)

@shared_task(name="app.workers.document_tasks.extract_document_task", bind=True)
def extract_document_task(self, document_id: int, user_id: int, fields: List[str] = None):
    """Extract data from document"""
    logger.info(f"Starting extraction task: document_id={document_id}")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(
            _extract_document_async(document_id, user_id, fields)
        )
        return result
    finally:
        loop.close()

async def _extract_document_async(document_id: int, user_id: int, fields: List[str] = None):
    """Async extraction implementation"""
    async with async_session_maker() as db:
        extraction_service = ExtractionService(db, get_ocr_factory(), get_cache_service())
        
        result = await extraction_service.extract_document_data(
            document_id, user_id, fields
        )
        
        return result

@shared_task(name="app.workers.document_tasks.classify_document_task")
def classify_document_task(document_id: int, user_id: int):
    """Classify document type"""
    logger.info(f"Starting classification task: document_id={document_id}")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(
            _classify_document_async(document_id, user_id)
        )
        return result
    finally:
        loop.close()

async def _classify_document_async(document_id: int, user_id: int):
    """Async classification implementation"""
    classification_service = ClassificationService(get_model_loader(), get_cache_service())
    
    result = await classification_service.classify_document(document_id, user_id)
    return result

@shared_task(name="app.workers.document_tasks.detect_fraud_task")
def detect_fraud_task(document_id: int, user_id: int):
    """Run fraud detection on document"""
    logger.info(f"Starting fraud detection task: document_id={document_id}")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        result = loop.run_until_complete(
            _detect_fraud_async(document_id, user_id)
        )
        return result
    finally:
        loop.close()

async def _detect_fraud_async(document_id: int, user_id: int):
    """Async fraud detection implementation"""
    async with async_session_maker() as db:
        fraud_service = FraudService(db, get_cache_service())
        
        result = await fraud_service.check_document_fraud(document_id, user_id)
        return result

@shared_task(name="app.workers.document_tasks.reprocess_document_task")
def reprocess_document_task(document_id: int, user_id: int):
    """Reprocess a document (re-run all steps)"""
    logger.info(f"Starting reprocessing task: document_id={document_id}")
    
    # Clear cache first
    cache = get_cache_service()
    if cache:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(cache.delete(f"doc_{document_id}_*"))
        finally:
            loop.close()
    
    # Re-run processing
    return process_document_task(document_id, user_id)

@shared_task(name="app.workers.document_tasks.cleanup_temp_files_task")
def cleanup_temp_files_task():
    """Clean up temporary files"""
    logger.info("Starting temp files cleanup")
    
    try:
        temp_dir = settings.TEMP_DIR
        if temp_dir.exists():
            # Delete files older than 24 hours
            cutoff = datetime.now().timestamp() - (24 * 3600)
            deleted_count = 0
            
            for file_path in temp_dir.iterdir():
                if file_path.is_file() and file_path.stat().st_mtime < cutoff:
                    file_path.unlink()
                    deleted_count += 1
            
            logger.info(f"Cleaned up {deleted_count} temp files")
            return {"deleted_count": deleted_count}
        
        return {"deleted_count": 0}
    
    except Exception as e:
        logger.error(f"Temp cleanup failed: {str(e)}")
        return {"error": str(e)}

@shared_task(name="app.workers.document_tasks.health_check_task")
def health_check_task():
    """Health check for Celery worker"""
    import psutil
    
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "memory_usage_mb": psutil.Process().memory_info().rss / (1024 * 1024),
        "cpu_percent": psutil.Process().cpu_percent()
    }

@shared_task(name="app.workers.document_tasks.refresh_models_task")
def refresh_models_task():
    """Refresh AI models (reload from disk)"""
    logger.info("Refreshing AI models")
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        # Reload models
        model_loader = get_model_loader()
        
        # Force reload
        loop.run_until_complete(model_loader.reload_model("bert_classifier"))
        loop.run_until_complete(model_loader.reload_model("ner_extractor"))
        
        logger.info("Models refreshed successfully")
        return {"success": True, "models_refreshed": ["bert_classifier", "ner_extractor"]}
    
    except Exception as e:
        logger.error(f"Model refresh failed: {str(e)}")
        return {"success": False, "error": str(e)}
    finally:
        loop.close()

@shared_task(name="app.workers.document_tasks.batch_upload_task")
def batch_upload_task(file_paths: List[str], user_id: int):
    """Process batch upload of multiple files"""
    logger.info(f"Starting batch upload: {len(file_paths)} files")
    
    results = []
    for file_path in file_paths:
        try:
            # Process each file
            # This would create document and process it
            results.append({
                "file_path": file_path,
                "status": "pending"
            })
        except Exception as e:
            results.append({
                "file_path": file_path,
                "status": "failed",
                "error": str(e)
            })
    
    return {
        "total": len(file_paths),
        "results": results
    }

def schedule_document_processing(document_id: int, user_id: int, delay_seconds: int = 0):
    """Schedule document processing with delay"""
    if delay_seconds > 0:
        process_document_task.apply_async(
            args=[document_id, user_id],
            countdown=delay_seconds
        )
    else:
        process_document_task.delay(document_id, user_id)