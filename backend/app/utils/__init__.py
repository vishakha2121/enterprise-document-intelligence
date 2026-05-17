"""
Utils Package
Utility functions, validators, decorators, and exceptions
"""

from app.utils.file_validator import FileValidator
from app.utils.logger import setup_logging, get_logger
from app.utils.helpers import (
    generate_id, calculate_hash, format_file_size,
    parse_date, sanitize_filename, chunk_list,
    retry_async, format_currency
)
from app.utils.decorators import (
    timing_decorator, log_execution, rate_limit,
    cache_result, handle_exceptions, validate_input
)
from app.utils.exceptions import (
    AppException,
    DocumentNotFoundError,
    ExtractionError,
    FraudDetectionError,
    StorageError,
    ValidationError,
    RateLimitError
)

__all__ = [
    # File Validator
    "FileValidator",
    # Logger
    "setup_logging",
    "get_logger",
    # Helpers
    "generate_id",
    "calculate_hash",
    "format_file_size",
    "parse_date",
    "sanitize_filename",
    "chunk_list",
    "retry_async",
    "format_currency",
    # Decorators
    "timing_decorator",
    "log_execution",
    "rate_limit",
    "cache_result",
    "handle_exceptions",
    "validate_input",
    # Exceptions
    "AppException",
    "DocumentNotFoundError",
    "ExtractionError",
    "FraudDetectionError",
    "StorageError",
    "ValidationError",
    "RateLimitError"
]