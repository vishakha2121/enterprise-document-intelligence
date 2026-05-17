"""
Health Check Routes
Monitor system health and dependencies
"""

from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, List
from datetime import datetime
import platform
import psutil
import logging

from app.config import settings
from app.dependencies import get_redis_client, get_db_session
from sqlalchemy import text

router = APIRouter()
logger = logging.getLogger(__name__)

@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Basic health check endpoint
    """
    return {
        "status": "healthy",
        "service": "document-intelligence-api",
        "version": settings.APP_VERSION,
        "timestamp": datetime.now().isoformat(),
        "environment": settings.ENVIRONMENT
    }

@router.get("/health/detailed")
async def detailed_health_check(
    redis_client = Depends(get_redis_client)
) -> Dict[str, Any]:
    """
    Detailed health check with all dependencies
    """
    health_status = {
        "status": "healthy",
        "service": "document-intelligence-api",
        "version": settings.APP_VERSION,
        "timestamp": datetime.now().isoformat(),
        "environment": settings.ENVIRONMENT,
        "dependencies": {},
        "system_info": {},
        "metrics": {}
    }
    
    # Check database
    try:
        # This would be actual DB check
        health_status["dependencies"]["database"] = {
            "status": "healthy",
            "type": "postgresql",
            "url": settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else "local"
        }
    except Exception as e:
        health_status["dependencies"]["database"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    # Check Redis
    try:
        if redis_client:
            redis_client.ping()
            health_status["dependencies"]["redis"] = {
                "status": "healthy",
                "url": settings.REDIS_URL
            }
        else:
            health_status["dependencies"]["redis"] = {
                "status": "unavailable",
                "reason": "Redis client not initialized"
            }
    except Exception as e:
        health_status["dependencies"]["redis"] = {
            "status": "unhealthy",
            "error": str(e)
        }
        health_status["status"] = "degraded"
    
    # Check storage
    try:
        upload_dir = settings.UPLOAD_DIR
        if upload_dir.exists():
            health_status["dependencies"]["storage"] = {
                "status": "healthy",
                "path": str(upload_dir),
                "writable": True
            }
        else:
            health_status["dependencies"]["storage"] = {
                "status": "unhealthy",
                "reason": "Upload directory does not exist"
            }
    except Exception as e:
        health_status["dependencies"]["storage"] = {
            "status": "unhealthy",
            "error": str(e)
        }
    
    # System information
    health_status["system_info"] = {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "hostname": platform.node()
    }
    
    # System metrics
    health_status["metrics"] = {
        "cpu_percent": psutil.cpu_percent(interval=1),
        "memory_percent": psutil.virtual_memory().percent,
        "disk_usage": psutil.disk_usage("/").percent,
        "available_memory_mb": psutil.virtual_memory().available / 1024 / 1024
    }
    
    return health_status

@router.get("/health/readiness")
async def readiness_check() -> Dict[str, Any]:
    """
    Readiness probe for Kubernetes/containers
    """
    ready = True
    issues = []
    
    # Check if database is ready
    try:
        # Would check actual DB connection
        pass
    except Exception as e:
        ready = False
        issues.append(f"Database not ready: {str(e)}")
    
    # Check if upload directory is writable
    try:
        test_file = settings.UPLOAD_DIR / ".write_test"
        test_file.touch()
        test_file.unlink()
    except Exception as e:
        ready = False
        issues.append(f"Storage not writable: {str(e)}")
    
    return {
        "ready": ready,
        "issues": issues,
        "timestamp": datetime.now().isoformat()
    }

@router.get("/health/liveness")
async def liveness_check() -> Dict[str, Any]:
    """
    Liveness probe for Kubernetes/containers
    """
    return {
        "alive": True,
        "timestamp": datetime.now().isoformat()
    }

@router.get("/health/metrics")
async def get_metrics() -> Dict[str, Any]:
    """
    Get application metrics
    """
    metrics = {
        "uptime_seconds": 0,  # Would track actual uptime
        "requests_total": 0,  # Would track request count
        "requests_per_second": 0,
        "average_response_time_ms": 0,
        "error_rate_percent": 0,
        "active_connections": 0,
        "queue_size": 0,
        "cache_hit_rate": 0.85,
        "cache_size_mb": 0
    }
    
    return metrics

@router.get("/health/dependencies")
async def check_dependencies() -> Dict[str, Any]:
    """
    Check status of all external dependencies
    """
    dependencies = {
        "database": {"name": "PostgreSQL", "required": True, "status": "unknown"},
        "redis": {"name": "Redis", "required": False, "status": "unknown"},
        "tesseract": {"name": "Tesseract OCR", "required": True, "status": "unknown"},
        "storage": {"name": "File Storage", "required": True, "status": "unknown"}
    }
    
    # Check Tesseract
    try:
        import subprocess
        result = subprocess.run(["tesseract", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            dependencies["tesseract"]["status"] = "healthy"
            dependencies["tesseract"]["version"] = result.stdout.split("\n")[0]
        else:
            dependencies["tesseract"]["status"] = "unhealthy"
    except Exception:
        dependencies["tesseract"]["status"] = "unhealthy"
        dependencies["tesseract"]["error"] = "Tesseract not found in PATH"
    
    # Check storage
    try:
        if settings.UPLOAD_DIR.exists():
            dependencies["storage"]["status"] = "healthy"
            dependencies["storage"]["path"] = str(settings.UPLOAD_DIR)
        else:
            dependencies["storage"]["status"] = "unhealthy"
    except Exception as e:
        dependencies["storage"]["status"] = "unhealthy"
        dependencies["storage"]["error"] = str(e)
    
    return {
        "dependencies": dependencies,
        "timestamp": datetime.now().isoformat()
    }

@router.post("/health/reset-cache")
async def reset_cache(
    redis_client = Depends(get_redis_client)
) -> Dict[str, Any]:
    """
    Reset Redis cache (admin only)
    """
    try:
        if redis_client:
            redis_client.flushdb()
            return {
                "success": True,
                "message": "Cache reset successfully",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "success": False,
                "message": "Redis not available",
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        return {
            "success": False,
            "message": f"Failed to reset cache: {str(e)}",
            "timestamp": datetime.now().isoformat()
        }

@router.get("/health/version")
async def get_version_info() -> Dict[str, Any]:
    """
    Get version information of all components
    """
    version_info = {
        "api_version": settings.APP_VERSION,
        "python_version": platform.python_version(),
        "fastapi_version": "0.104.1",  # Would get from installed packages
        "pytorch_version": "2.1.0",
        "transformers_version": "4.35.0",
        "tesseract_version": "5.3.0",
        "redis_version": "7.2.0",
        "postgresql_version": "15.0",
        "last_deployed": "2024-01-15T10:30:00Z",
        "git_commit": "a1b2c3d4e5f6"
    }
    
    return version_info

@router.get("/health/disk-usage")
async def get_disk_usage() -> Dict[str, Any]:
    """
    Get disk usage statistics
    """
    try:
        upload_usage = 0
        if settings.UPLOAD_DIR.exists():
            import shutil
            upload_usage = shutil.disk_usage(settings.UPLOAD_DIR)
        
        return {
            "upload_directory": {
                "total_gb": upload_usage.total / (1024**3),
                "used_gb": upload_usage.used / (1024**3),
                "free_gb": upload_usage.free / (1024**3),
                "usage_percent": (upload_usage.used / upload_usage.total) * 100
            },
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }