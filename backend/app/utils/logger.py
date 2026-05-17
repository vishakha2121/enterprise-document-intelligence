"""
Logging Configuration
Structured logging with rotation and multiple handlers
"""

import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from datetime import datetime
import json
from typing import Dict, Any
import traceback

from app.config import settings

# Log format strings
CONSOLE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
FILE_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s"
JSON_FORMAT = "%(message)s"

class JSONFormatter(logging.Formatter):
    """JSON formatted logger for structured logging"""
    
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        
        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": str(record.exc_info[1]),
                "traceback": traceback.format_exception(*record.exc_info)
            }
        
        # Add extra fields
        if hasattr(record, 'extra_data'):
            log_entry["extra"] = record.extra_data
        
        return json.dumps(log_entry)

class StructuredLogger:
    """Structured logger with context support"""
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
        self._context: Dict[str, Any] = {}
    
    def set_context(self, **kwargs):
        """Set logging context"""
        self._context.update(kwargs)
    
    def clear_context(self):
        """Clear logging context"""
        self._context.clear()
    
    def _log(self, level: int, msg: str, *args, **kwargs):
        """Internal log method with context"""
        extra = kwargs.pop('extra', {})
        extra.update(self._context)
        
        # Add extra_data to record
        if extra:
            kwargs['extra'] = {'extra_data': extra}
        
        self.logger.log(level, msg, *args, **kwargs)
    
    def debug(self, msg: str, *args, **kwargs):
        self._log(logging.DEBUG, msg, *args, **kwargs)
    
    def info(self, msg: str, *args, **kwargs):
        self._log(logging.INFO, msg, *args, **kwargs)
    
    def warning(self, msg: str, *args, **kwargs):
        self._log(logging.WARNING, msg, *args, **kwargs)
    
    def error(self, msg: str, *args, **kwargs):
        self._log(logging.ERROR, msg, *args, **kwargs)
    
    def critical(self, msg: str, *args, **kwargs):
        self._log(logging.CRITICAL, msg, *args, **kwargs)
    
    def exception(self, msg: str, *args, **kwargs):
        self._log(logging.ERROR, msg, *args, exc_info=True, **kwargs)

def setup_logging():
    """Setup logging configuration"""
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)
    
    # Get log level from settings
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    
    # Root logger configuration
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    root_logger.handlers.clear()
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_formatter = logging.Formatter(CONSOLE_FORMAT)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler - rotating by size
    file_handler = RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(FILE_FORMAT)
    file_handler.setFormatter(file_formatter)
    root_logger.addHandler(file_handler)
    
    # Error file handler
    error_handler = RotatingFileHandler(
        log_dir / "error.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    root_logger.addHandler(error_handler)
    
    # JSON log handler for structured logging
    json_handler = TimedRotatingFileHandler(
        log_dir / "structured.log",
        when="midnight",
        interval=1,
        backupCount=7
    )
    json_handler.setLevel(logging.INFO)
    json_formatter = JSONFormatter()
    json_handler.setFormatter(json_formatter)
    root_logger.addHandler(json_handler)
    
    # Set log levels for third-party libraries
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("aiosqlite").setLevel(logging.WARNING)
    
    # Log startup
    logger = logging.getLogger(__name__)
    logger.info(f"Logging configured. Level: {settings.LOG_LEVEL}")
    logger.info(f"Log directory: {log_dir.absolute()}")
    
    return root_logger

def get_logger(name: str) -> StructuredLogger:
    """
    Get structured logger for a module
    
    Args:
        name: Logger name (usually __name__)
    
    Returns:
        StructuredLogger instance
    """
    return StructuredLogger(name)

# Request logger middleware helper
def log_request(request, response_time: float = None):
    """Log HTTP request details"""
    logger = logging.getLogger("api.request")
    
    log_data = {
        "method": request.method,
        "url": str(request.url),
        "client_ip": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "response_time_ms": round(response_time * 1000, 2) if response_time else None
    }
    
    if response_time:
        logger.info(f"Request completed", extra={"extra_data": log_data})
    else:
        logger.info(f"Incoming request", extra={"extra_data": log_data})

def log_performance(operation: str, duration_ms: float, details: Dict = None):
    """Log performance metrics"""
    logger = logging.getLogger("performance")
    
    log_data = {
        "operation": operation,
        "duration_ms": round(duration_ms, 2),
        "details": details or {}
    }
    
    if duration_ms > 1000:
        logger.warning(f"Slow operation detected", extra={"extra_data": log_data})
    else:
        logger.debug(f"Performance metric", extra={"extra_data": log_data})

def log_security_event(event_type: str, user_id: int = None, details: Dict = None):
    """Log security-related events"""
    logger = logging.getLogger("security")
    
    log_data = {
        "event_type": event_type,
        "user_id": user_id,
        "details": details or {},
        "timestamp": datetime.utcnow().isoformat()
    }
    
    logger.info(f"Security event: {event_type}", extra={"extra_data": log_data})