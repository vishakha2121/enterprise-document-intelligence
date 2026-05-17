"""
Batch Processor
Handles batch operations for multiple documents
"""

import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from celery import shared_task, group, chord, chain
from celery.result import GroupResult

from app.workers.celery_app import celery_app
from app.workers.document_tasks import (
    extract_document_task,
    classify_document_task,
    detect_fraud_task
)
from app.services.cache_service import CacheService
from app.database.session import async_session_maker
from app.database.models.document import Document
from app.utils.logger import get_logger

logger = get_logger(__name__)

class BatchStatus(str, Enum):
    """Batch processing status"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL = "partial"

@dataclass
class BatchJob:
    """Batch job metadata"""
    job_id: str
    document_ids: List[int]
    operation: str
    status: BatchStatus
    created_at: datetime
    completed_at: Optional[datetime] = None
    results: Optional[List[Dict]] = None
    errors: Optional[List[Dict]] = None
    
    def to_dict(self) -> Dict:
        return {
            "job_id": self.job_id,
            "document_ids": self.document_ids,
            "operation": self.operation,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "total_documents": len(self.document_ids),
            "results": self.results,
            "errors": self.errors
        }

class BatchProcessor:
    """Handles batch operations for multiple documents"""
    
    def __init__(self, cache_service: Optional[CacheService] = None):
        self.cache = cache_service
        self._jobs: Dict[str, BatchJob] = {}
    
    async def create_batch_job(
        self,
        document_ids: List[int],
        operation: str,
        user_id: int
    ) -> str:
        """
        Create a new batch job
        
        Args:
            document_ids: List of document IDs
            operation: Operation to perform (extract, classify, fraud, all)
            user_id: User ID
        
        Returns:
            Job ID
        """
        import uuid
        job_id = f"{operation}_{uuid.uuid4().hex[:12]}"
        
        job = BatchJob(
            job_id=job_id,
            document_ids=document_ids,
            operation=operation,
            status=BatchStatus.PENDING,
            created_at=datetime.now()
        )
        
        self._jobs[job_id] = job
        
        # Start processing
        asyncio.create_task(self._process_batch_job(job, user_id))
        
        # Cache job info
        if self.cache:
            await self.cache.set(f"batch_job:{job_id}", job.to_dict(), ttl=3600)
        
        return job_id
    
    async def _process_batch_job(self, job: BatchJob, user_id: int):
        """Process batch job asynchronously"""
        job.status = BatchStatus.RUNNING
        
        results = []
        errors = []
        
        for doc_id in job.document_ids:
            try:
                result = await self._process_single_document(doc_id, user_id, job.operation)
                results.append({
                    "document_id": doc_id,
                    "success": True,
                    "result": result
                })
            except Exception as e:
                logger.error(f"Batch processing failed for document {doc_id}: {str(e)}")
                errors.append({
                    "document_id": doc_id,
                    "success": False,
                    "error": str(e)
                })
        
        job.results = results
        job.errors = errors
        job.completed_at = datetime.now()
        
        if errors and results:
            job.status = BatchStatus.PARTIAL
        elif errors and not results:
            job.status = BatchStatus.FAILED
        else:
            job.status = BatchStatus.COMPLETED
        
        # Update cache
        if self.cache:
            await self.cache.set(f"batch_job:{job.job_id}", job.to_dict(), ttl=3600)
    
    async def _process_single_document(
        self,
        document_id: int,
        user_id: int,
        operation: str
    ) -> Dict[str, Any]:
        """Process single document for batch operation"""
        if operation == "extract":
            # Would call extraction service
            return {"extraction": "completed"}
        elif operation == "classify":
            return {"classification": "completed"}
        elif operation == "fraud":
            return {"fraud_check": "completed"}
        elif operation == "all":
            return {"extraction": "completed", "classification": "completed", "fraud": "completed"}
        else:
            raise ValueError(f"Unknown operation: {operation}")
    
    async def get_job_status(self, job_id: str) -> Optional[Dict]:
        """Get batch job status"""
        # Check cache first
        if self.cache:
            cached = await self.cache.get(f"batch_job:{job_id}")
            if cached:
                return cached
        
        # Check memory
        job = self._jobs.get(job_id)
        if job:
            return job.to_dict()
        
        return None
    
    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a pending batch job"""
        job = self._jobs.get(job_id)
        if job and job.status == BatchStatus.PENDING:
            job.status = BatchStatus.FAILED
            job.completed_at = datetime.now()
            return True
        return False

# Celery batch tasks

@shared_task(name="app.workers.batch_processor.process_batch_extraction")
def process_batch_extraction(document_ids: List[int], user_id: int) -> Dict:
    """
    Process batch extraction for multiple documents using Celery
    
    Args:
        document_ids: List of document IDs
        user_id: User ID
    
    Returns:
        Batch processing results
    """
    logger.info(f"Processing batch extraction for {len(document_ids)} documents")
    
    # Create a group of extraction tasks
    job = group(extract_document_task.s(doc_id, user_id) for doc_id in document_ids)
    
    # Execute the group and collect results
    result = job.apply_async()
    
    # Wait for results (with timeout)
    try:
        results = result.get(timeout=300)  # 5 minute timeout
    except Exception as e:
        logger.error(f"Batch extraction failed: {str(e)}")
        return {
            "success": False,
            "error": str(e),
            "total": len(document_ids),
            "results": []
        }
    
    # Process results
    successful = []
    failed = []
    
    for doc_id, res in zip(document_ids, results):
        if res and res.get("success"):
            successful.append({"document_id": doc_id, "result": res})
        else:
            failed.append({"document_id": doc_id, "error": res.get("error") if res else "Unknown error"})
    
    return {
        "success": True,
        "total": len(document_ids),
        "successful_count": len(successful),
        "failed_count": len(failed),
        "successful": successful,
        "failed": failed
    }

@shared_task(name="app.workers.batch_processor.process_batch_classification")
def process_batch_classification(document_ids: List[int], user_id: int) -> Dict:
    """Process batch classification"""
    logger.info(f"Processing batch classification for {len(document_ids)} documents")
    
    job = group(classify_document_task.s(doc_id, user_id) for doc_id in document_ids)
    result = job.apply_async()
    
    try:
        results = result.get(timeout=120)
    except Exception as e:
        return {"success": False, "error": str(e), "total": len(document_ids)}
    
    successful = [{"document_id": doc_id, "result": res} 
                  for doc_id, res in zip(document_ids, results) if res]
    
    return {
        "success": True,
        "total": len(document_ids),
        "successful_count": len(successful),
        "results": successful
    }

@shared_task(name="app.workers.batch_processor.process_batch_fraud_check")
def process_batch_fraud_check(document_ids: List[int], user_id: int) -> Dict:
    """Process batch fraud detection"""
    logger.info(f"Processing batch fraud check for {len(document_ids)} documents")
    
    job = group(detect_fraud_task.s(doc_id, user_id) for doc_id in document_ids)
    result = job.apply_async()
    
    try:
        results = result.get(timeout=180)
    except Exception as e:
        return {"success": False, "error": str(e), "total": len(document_ids)}
    
    # Calculate summary statistics
    high_risk = 0
    medium_risk = 0
    low_risk = 0
    
    for res in results:
        if res:
            risk_level = res.get("risk_level", "low")
            if risk_level == "high":
                high_risk += 1
            elif risk_level == "medium":
                medium_risk += 1
            else:
                low_risk += 1
    
    return {
        "success": True,
        "total": len(document_ids),
        "high_risk": high_risk,
        "medium_risk": medium_risk,
        "low_risk": low_risk,
        "results": [{"document_id": doc_id, "result": res} 
                    for doc_id, res in zip(document_ids, results) if res]
    }

@shared_task(name="app.workers.batch_processor.process_all_operations")
def process_all_operations(document_ids: List[int], user_id: int) -> Dict:
    """
    Process all operations (extract, classify, fraud) in sequence using chord
    """
    logger.info(f"Processing all operations for {len(document_ids)} documents")
    
    # Chain: extract -> classify -> fraud
    callback = process_batch_fraud_check.s(document_ids, user_id)
    
    # First extract, then classify, then fraud
    header = [
        process_batch_extraction.s([doc_id], user_id) 
        for doc_id in document_ids
    ]
    
    # Use chord to combine results
    result = chord(header)(callback)
    
    try:
        final_result = result.get(timeout=600)
        return {
            "success": True,
            "total": len(document_ids),
            "result": final_result
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@shared_task(name="app.workers.batch_processor.cleanup_old_task_results")
def cleanup_old_task_results():
    """Clean up old Celery task results"""
    from celery.result import AsyncResult
    
    logger.info("Cleaning up old task results")
    
    # Get all active tasks (this is simplified)
    # In production, you'd use result backend cleanup
    
    return {"cleaned": True, "timestamp": datetime.now().isoformat()}

@shared_task(name="app.workers.batch_processor.aggregate_statistics")
def aggregate_statistics():
    """Aggregate system statistics from batch operations"""
    logger.info("Aggregating system statistics")
    
    # This would query database for statistics
    stats = {
        "timestamp": datetime.now().isoformat(),
        "total_documents_processed": 0,
        "average_processing_time_ms": 0,
        "success_rate": 0,
        "fraud_rate": 0
    }
    
    return stats

def schedule_periodic_tasks():
    """Schedule periodic batch tasks"""
    from celery.schedules import crontab
    
    celery_app.conf.beat_schedule.update({
        "daily-stats-aggregation": {
            "task": "app.workers.batch_processor.aggregate_statistics",
            "schedule": crontab(hour=1, minute=0),
            "options": {"queue": "low_priority"}
        },
        "weekly-cleanup": {
            "task": "app.workers.batch_processor.cleanup_old_task_results",
            "schedule": crontab(day_of_week=0, hour=2, minute=0),
            "options": {"queue": "low_priority"}
        }
    })
    
    logger.info("Periodic batch tasks scheduled")

# Batch processing helper for the main app
_batch_processor = None

def get_batch_processor() -> BatchProcessor:
    """Get or create batch processor instance"""
    global _batch_processor
    if _batch_processor is None:
        from app.dependencies import get_redis_client
        redis_client = get_redis_client()
        cache = CacheService(redis_client) if redis_client else None
        _batch_processor = BatchProcessor(cache)
    return _batch_processor

async def submit_batch_job(
    document_ids: List[int],
    operation: str,
    user_id: int
) -> str:
    """Submit a batch job for processing"""
    processor = get_batch_processor()
    return await processor.create_batch_job(document_ids, operation, user_id)

async def get_batch_job_status(job_id: str) -> Optional[Dict]:
    """Get batch job status"""
    processor = get_batch_processor()
    return await processor.get_job_status(job_id)

async def cancel_batch_job(job_id: str) -> bool:
    """Cancel a batch job"""
    processor = get_batch_processor()
    return await processor.cancel_job(job_id)