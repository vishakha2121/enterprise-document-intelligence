"""
Workers Package
Background task processing with Celery
"""

from app.workers.celery_app import celery_app, celery_worker
from app.workers.document_tasks import (
    process_document_task,
    extract_document_task,
    classify_document_task,
    detect_fraud_task,
    reprocess_document_task,
    cleanup_temp_files_task
)
from app.workers.batch_processor import (
    BatchProcessor,
    process_batch_extraction,
    process_batch_classification,
    process_batch_fraud_check,
    schedule_periodic_tasks
)

__all__ = [
    # Celery
    "celery_app",
    "celery_worker",
    # Document tasks
    "process_document_task",
    "extract_document_task",
    "classify_document_task",
    "detect_fraud_task",
    "reprocess_document_task",
    "cleanup_temp_files_task",
    # Batch processor
    "BatchProcessor",
    "process_batch_extraction",
    "process_batch_classification",
    "process_batch_fraud_check",
    "schedule_periodic_tasks"
]