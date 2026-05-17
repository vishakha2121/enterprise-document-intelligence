"""
Celery Configuration
Async task queue setup for background processing
"""

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init, worker_process_shutdown
import logging
import asyncio
from pathlib import Path
import sys

from app.config import settings

logger = logging.getLogger(__name__)

# Create Celery app
celery_app = Celery(
    "document_intelligence",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.document_tasks",
        "app.workers.batch_processor"
    ]
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    
    # Task execution
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    
    # Rate limits
    task_annotations={
        "app.workers.document_tasks.process_document_task": {"rate_limit": "10/m"},
        "app.workers.document_tasks.extract_document_task": {"rate_limit": "20/m"},
        "app.workers.document_tasks.classify_document_task": {"rate_limit": "30/m"},
        "app.workers.document_tasks.detect_fraud_task": {"rate_limit": "15/m"},
    },
    
    # Result settings
    result_expires=3600 * 24,  # 24 hours
    result_backend_transport_options={
        "retry_policy": {
            "timeout": 5.0,
            "max_retries": 3
        }
    },
    
    # Worker settings
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=100,
    worker_max_memory_per_child=200 * 1024 * 1024,  # 200MB
    
    # Queue settings
    task_queues={
        "default": {
            "exchange": "default",
            "routing_key": "default",
        },
        "high_priority": {
            "exchange": "high_priority",
            "routing_key": "high_priority",
        },
        "low_priority": {
            "exchange": "low_priority",
            "routing_key": "low_priority",
        },
        "batch": {
            "exchange": "batch",
            "routing_key": "batch",
        },
    },
    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",
    
    # Routing
    task_routes={
        "app.workers.document_tasks.process_document_task": {"queue": "high_priority"},
        "app.workers.document_tasks.extract_document_task": {"queue": "high_priority"},
        "app.workers.batch_processor.process_batch_extraction": {"queue": "batch"},
        "app.workers.batch_processor.process_batch_classification": {"queue": "batch"},
    },
)

# Periodic tasks (Celery Beat)
celery_app.conf.beat_schedule = {
    # Cleanup tasks
    "cleanup-temp-files": {
        "task": "app.workers.document_tasks.cleanup_temp_files_task",
        "schedule": crontab(hour=2, minute=0),  # Daily at 2 AM
        "options": {"queue": "low_priority"}
    },
    "cleanup-old-tasks": {
        "task": "app.workers.batch_processor.cleanup_old_task_results",
        "schedule": crontab(hour=3, minute=0),  # Daily at 3 AM
        "options": {"queue": "low_priority"}
    },
    # Health check
    "health-check": {
        "task": "app.workers.document_tasks.health_check_task",
        "schedule": crontab(minute="*/5"),  # Every 5 minutes
        "options": {"queue": "default"}
    },
    # Statistics aggregation
    "aggregate-stats": {
        "task": "app.workers.batch_processor.aggregate_statistics",
        "schedule": crontab(minute="*/15"),  # Every 15 minutes
        "options": {"queue": "low_priority"}
    },
    # Model refresh (if needed)
    "refresh-models": {
        "task": "app.workers.document_tasks.refresh_models_task",
        "schedule": crontab(hour=4, minute=0),  # Daily at 4 AM
        "options": {"queue": "low_priority"}
    },
}

# Configure logging for Celery
def setup_celery_logging():
    """Setup logging for Celery workers"""
    from app.utils.logger import setup_logging
    setup_logging()

@worker_process_init.connect
def init_worker(**kwargs):
    """Initialize worker process"""
    setup_celery_logging()
    logger.info("Celery worker process initialized")

@worker_process_shutdown.connect
def shutdown_worker(**kwargs):
    """Shutdown worker process"""
    logger.info("Celery worker process shutting down")

def celery_worker():
    """Run Celery worker"""
    argv = [
        "worker",
        "--loglevel=INFO",
        "--concurrency=4",
        "--max-tasks-per-child=100",
        "--max-memory-per-child=200000",
        "-Q",
        "default,high_priority,low_priority,batch"
    ]
    
    # Add pool type based on platform
    import platform
    if platform.system() == "Windows":
        argv.append("--pool=solo")  # Solo pool for Windows
    
    celery_app.worker_main(argv)

def celery_beat():
    """Run Celery beat scheduler"""
    argv = [
        "beat",
        "--loglevel=INFO",
        "--schedule=/tmp/celerybeat-schedule"
    ]
    celery_app.worker_main(argv)

def celery_flower():
    """Run Flower monitoring"""
    try:
        from flower.command import FlowerCommand
        flower = FlowerCommand()
        flower.execute_from_commandline([
            "flower",
            "--broker=" + settings.CELERY_BROKER_URL,
            "--port=5555",
            "--address=0.0.0.0"
        ])
    except ImportError:
        logger.warning("Flower not installed. Install with: pip install flower")

# Task base class with error handling
class BaseTask(celery_app.Task):
    """Base task class with error handling and logging"""
    
    abstract = True
    max_retries = 3
    default_retry_delay = 60  # seconds
    
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Handle task failure"""
        logger.error(
            f"Task {self.name} failed: {str(exc)}",
            extra={
                "task_id": task_id,
                "args": args,
                "kwargs": kwargs
            }
        )
        super().on_failure(exc, task_id, args, kwargs, einfo)
    
    def on_success(self, retval, task_id, args, kwargs):
        """Handle task success"""
        logger.info(
            f"Task {self.name} completed successfully",
            extra={
                "task_id": task_id,
                "result": str(retval)[:200]  # Truncate long results
            }
        )
    
    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """Handle task retry"""
        logger.warning(
            f"Task {self.name} retrying: {str(exc)}",
            extra={
                "task_id": task_id,
                "retry_count": self.request.retries
            }
        )

# Set base task class
celery_app.Task = BaseTask

# Helper function to check Celery status
def celery_status() -> dict:
    """Check Celery worker status"""
    try:
        i = celery_app.control.inspect()
        stats = i.stats()
        active = i.active()
        scheduled = i.scheduled()
        
        return {
            "available": True,
            "workers": list(stats.keys()) if stats else [],
            "active_tasks": len(active) if active else 0,
            "scheduled_tasks": len(scheduled) if scheduled else 0,
            "stats": stats
        }
    except Exception as e:
        logger.error(f"Celery status check failed: {str(e)}")
        return {
            "available": False,
            "error": str(e)
        }

def get_task_result(task_id: str) -> dict:
    """Get task result by ID"""
    try:
        result = celery_app.AsyncResult(task_id)
        return {
            "task_id": task_id,
            "status": result.status,
            "ready": result.ready(),
            "successful": result.successful() if result.ready() else None,
            "result": result.result if result.ready() else None,
            "traceback": result.traceback if result.failed() else None
        }
    except Exception as e:
        return {
            "task_id": task_id,
            "error": str(e)
        }

def revoke_task(task_id: str, terminate: bool = False):
    """Revoke a running task"""
    try:
        celery_app.control.revoke(task_id, terminate=terminate)
        return {"success": True, "task_id": task_id}
    except Exception as e:
        return {"success": False, "error": str(e)}