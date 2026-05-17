"""
Custom Decorators
Reusable decorators for common functionality
"""

import functools
import time
import logging
from typing import Callable, Any, Optional, Dict, List, Type
from datetime import datetime
import asyncio
from functools import wraps

from app.utils.logger import log_performance

logger = logging.getLogger(__name__)

def timing_decorator(operation_name: str = None):
    """
    Decorator to measure execution time
    
    Args:
        operation_name: Name of the operation (defaults to function name)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                duration_ms = (time.time() - start_time) * 1000
                name = operation_name or func.__name__
                log_performance(name, duration_ms)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                duration_ms = (time.time() - start_time) * 1000
                name = operation_name or func.__name__
                log_performance(name, duration_ms)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator

def log_execution(level: str = "INFO"):
    """
    Decorator to log function execution
    
    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            log_level = getattr(logging, level.upper(), logging.INFO)
            logger.log(log_level, f"Executing: {func.__name__}")
            
            try:
                result = await func(*args, **kwargs)
                logger.log(log_level, f"Completed: {func.__name__}")
                return result
            except Exception as e:
                logger.error(f"Failed: {func.__name__} - {str(e)}")
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            log_level = getattr(logging, level.upper(), logging.INFO)
            logger.log(log_level, f"Executing: {func.__name__}")
            
            try:
                result = func(*args, **kwargs)
                logger.log(log_level, f"Completed: {func.__name__}")
                return result
            except Exception as e:
                logger.error(f"Failed: {func.__name__} - {str(e)}")
                raise
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator

def rate_limit(requests_per_minute: int = 60):
    """
    Decorator for rate limiting
    
    Args:
        requests_per_minute: Maximum requests per minute
    """
    from collections import defaultdict
    from datetime import datetime, timedelta
    
    call_history = defaultdict(list)
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            now = datetime.now()
            minute_ago = now - timedelta(minutes=1)
            
            # Clean old history
            call_history[func.__name__] = [
                t for t in call_history[func.__name__] 
                if t > minute_ago
            ]
            
            # Check limit
            if len(call_history[func.__name__]) >= requests_per_minute:
                from app.utils.exceptions import RateLimitError
                raise RateLimitError(f"Rate limit exceeded: {requests_per_minute} requests per minute")
            
            call_history[func.__name__].append(now)
            return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            now = datetime.now()
            minute_ago = now - timedelta(minutes=1)
            
            # Clean old history
            call_history[func.__name__] = [
                t for t in call_history[func.__name__] 
                if t > minute_ago
            ]
            
            # Check limit
            if len(call_history[func.__name__]) >= requests_per_minute:
                from app.utils.exceptions import RateLimitError
                raise RateLimitError(f"Rate limit exceeded: {requests_per_minute} requests per minute")
            
            call_history[func.__name__].append(now)
            return func(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator

def cache_result(ttl_seconds: int = 300, key_prefix: str = None):
    """
    Decorator to cache function results
    
    Args:
        ttl_seconds: Cache TTL in seconds
        key_prefix: Prefix for cache key
    """
    from functools import wraps
    import hashlib
    import json
    
    cache = {}
    
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate cache key
            key_data = {
                "func": func.__name__,
                "args": str(args),
                "kwargs": str(sorted(kwargs.items()))
            }
            key = hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
            if key_prefix:
                key = f"{key_prefix}:{key}"
            
            # Check cache
            if key in cache:
                cached_time, cached_value = cache[key]
                if time.time() - cached_time < ttl_seconds:
                    return cached_value
            
            # Execute and cache
            result = await func(*args, **kwargs)
            cache[key] = (time.time(), result)
            return result
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Generate cache key
            key_data = {
                "func": func.__name__,
                "args": str(args),
                "kwargs": str(sorted(kwargs.items()))
            }
            key = hashlib.md5(json.dumps(key_data, sort_keys=True).encode()).hexdigest()
            if key_prefix:
                key = f"{key_prefix}:{key}"
            
            # Check cache
            if key in cache:
                cached_time, cached_value = cache[key]
                if time.time() - cached_time < ttl_seconds:
                    return cached_value
            
            # Execute and cache
            result = func(*args, **kwargs)
            cache[key] = (time.time(), result)
            return result
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator

def handle_exceptions(
    fallback_return: Any = None,
    log_error: bool = True,
    raise_exceptions: List[Type[Exception]] = None
):
    """
    Decorator to handle exceptions gracefully
    
    Args:
        fallback_return: Value to return on exception
        log_error: Whether to log the error
        raise_exceptions: Exceptions that should still be raised
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if raise_exceptions and isinstance(e, tuple(raise_exceptions)):
                    raise
                if log_error:
                    logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
                return fallback_return
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if raise_exceptions and isinstance(e, tuple(raise_exceptions)):
                    raise
                if log_error:
                    logger.error(f"Error in {func.__name__}: {str(e)}", exc_info=True)
                return fallback_return
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator

def validate_input(**validators):
    """
    Decorator to validate function inputs
    
    Args:
        validators: Dictionary mapping parameter names to validation functions
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Bind arguments
            import inspect
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            # Validate each parameter
            for param_name, validator in validators.items():
                if param_name in bound_args.arguments:
                    value = bound_args.arguments[param_name]
                    if not validator(value):
                        from app.utils.exceptions import ValidationError
                        raise ValidationError(f"Validation failed for parameter '{param_name}': {value}")
            
            return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Bind arguments
            import inspect
            sig = inspect.signature(func)
            bound_args = sig.bind(*args, **kwargs)
            bound_args.apply_defaults()
            
            # Validate each parameter
            for param_name, validator in validators.items():
                if param_name in bound_args.arguments:
                    value = bound_args.arguments[param_name]
                    if not validator(value):
                        from app.utils.exceptions import ValidationError
                        raise ValidationError(f"Validation failed for parameter '{param_name}': {value}")
            
            return func(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator

def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Decorator to retry function on failure
    
    Args:
        max_attempts: Maximum number of attempts
        delay: Initial delay in seconds
        backoff: Multiplier for delay after each attempt
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff
            
            raise last_exception
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay
            
            for attempt in range(max_attempts):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        time.sleep(current_delay)
                        current_delay *= backoff
            
            raise last_exception
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator

def require_role(roles: List[str]):
    """
    Decorator to require specific user roles
    
    Args:
        roles: List of allowed roles
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Get user from kwargs (assumes user is passed as 'current_user')
            user = kwargs.get('current_user')
            if not user or user.get('role') not in roles:
                from app.utils.exceptions import PermissionError
                raise PermissionError(f"Role required: {', '.join(roles)}")
            return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            user = kwargs.get('current_user')
            if not user or user.get('role') not in roles:
                from app.utils.exceptions import PermissionError
                raise PermissionError(f"Role required: {', '.join(roles)}")
            return func(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper
    
    return decorator