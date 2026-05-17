"""
Helper Functions
Common utility functions used across the application
"""

import hashlib
import re
import uuid
from datetime import datetime, date
from typing import List, TypeVar, Callable, Any, Dict, Optional, Union
from decimal import Decimal
import asyncio
from functools import wraps
import secrets
import string

T = TypeVar('T')

def generate_id(prefix: str = "", length: int = 8) -> str:
    """
    Generate a unique ID
    
    Args:
        prefix: Optional prefix for the ID
        length: Length of random part
    
    Returns:
        Unique ID string
    """
    random_part = secrets.token_hex(length // 2)
    if prefix:
        return f"{prefix}_{random_part}"
    return random_part

def generate_api_key() -> str:
    """Generate a secure API key"""
    return secrets.token_urlsafe(32)

def calculate_hash(content: bytes, algorithm: str = "sha256") -> str:
    """
    Calculate hash of content
    
    Args:
        content: Bytes content to hash
        algorithm: Hash algorithm (sha256, md5, sha1)
    
    Returns:
        Hexadecimal hash string
    """
    if algorithm == "sha256":
        return hashlib.sha256(content).hexdigest()
    elif algorithm == "md5":
        return hashlib.md5(content).hexdigest()
    elif algorithm == "sha1":
        return hashlib.sha1(content).hexdigest()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

def format_file_size(size_bytes: int) -> str:
    """
    Format file size to human readable format
    
    Args:
        size_bytes: Size in bytes
    
    Returns:
        Formatted string (e.g., "1.5 MB")
    """
    if size_bytes == 0:
        return "0 B"
    
    size_names = ["B", "KB", "MB", "GB", "TB"]
    i = 0
    size = float(size_bytes)
    
    while size >= 1024 and i < len(size_names) - 1:
        size /= 1024
        i += 1
    
    return f"{size:.1f} {size_names[i]}"

def parse_date(date_string: str, formats: List[str] = None) -> Optional[date]:
    """
    Parse date from string using multiple formats
    
    Args:
        date_string: Date string to parse
        formats: List of date formats to try
    
    Returns:
        Parsed date or None
    """
    if not date_string:
        return None
    
    if formats is None:
        formats = [
            "%Y-%m-%d",
            "%d/%m/%Y",
            "%m/%d/%Y",
            "%d-%m-%Y",
            "%m-%d-%Y",
            "%d.%m.%Y",
            "%B %d, %Y",
            "%d %B %Y"
        ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_string.strip(), fmt).date()
        except ValueError:
            continue
    
    return None

def sanitize_filename(filename: str) -> str:
    """
    Sanitize filename to be safe for file system
    
    Args:
        filename: Original filename
    
    Returns:
        Sanitized filename
    """
    # Remove path separators
    filename = filename.replace('/', '_').replace('\\', '_')
    
    # Remove unsafe characters
    unsafe_chars = '<>:"|?*'
    for char in unsafe_chars:
        filename = filename.replace(char, '_')
    
    # Remove control characters
    filename = ''.join(char for char in filename if ord(char) >= 32)
    
    # Limit length
    if len(filename) > 255:
        name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
        filename = name[:250] + ('.' + ext if ext else '')
    
    # Remove leading/trailing spaces and dots
    filename = filename.strip('. ')
    
    return filename or "unnamed_file"

def chunk_list(items: List[T], chunk_size: int) -> List[List[T]]:
    """
    Split a list into chunks
    
    Args:
        items: List to split
        chunk_size: Size of each chunk
    
    Returns:
        List of chunks
    """
    return [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]

async def retry_async(
    func: Callable,
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Any:
    """
    Retry an async function with exponential backoff
    
    Args:
        func: Async function to retry
        max_retries: Maximum number of retries
        delay: Initial delay in seconds
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch
    
    Returns:
        Result of the function
    """
    last_exception = None
    current_delay = delay
    
    for attempt in range(max_retries):
        try:
            return await func()
        except exceptions as e:
            last_exception = e
            if attempt < max_retries - 1:
                await asyncio.sleep(current_delay)
                current_delay *= backoff
    
    raise last_exception

def format_currency(amount: Union[int, float, Decimal], currency: str = "INR") -> str:
    """
    Format amount as currency string
    
    Args:
        amount: Amount to format
        currency: Currency code (INR, USD, EUR, GBP)
    
    Returns:
        Formatted currency string
    """
    symbols = {
        "INR": "₹",
        "USD": "$",
        "EUR": "€",
        "GBP": "£"
    }
    
    symbol = symbols.get(currency.upper(), currency)
    
    if isinstance(amount, Decimal):
        amount = float(amount)
    
    # Format with 2 decimal places
    formatted = f"{amount:,.2f}"
    
    # Remove decimal if .00
    if formatted.endswith(".00"):
        formatted = formatted[:-3]
    
    return f"{symbol}{formatted}"

def mask_sensitive_data(data: str, visible_start: int = 4, visible_end: int = 4) -> str:
    """
    Mask sensitive data like API keys, passwords
    
    Args:
        data: Original string
        visible_start: Number of characters to show at start
        visible_end: Number of characters to show at end
    
    Returns:
        Masked string
    """
    if not data:
        return ""
    
    if len(data) <= visible_start + visible_end:
        return "*" * len(data)
    
    start = data[:visible_start]
    end = data[-visible_end:] if visible_end > 0 else ""
    masked = "*" * (len(data) - visible_start - visible_end)
    
    return f"{start}{masked}{end}"

def is_valid_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def is_valid_phone(phone: str) -> bool:
    """Validate phone number format"""
    # Remove common separators
    cleaned = re.sub(r'[\s\-\(\)\+]', '', phone)
    # Check if it's a valid phone number (basic check)
    return cleaned.isdigit() and 10 <= len(cleaned) <= 15

def truncate_string(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """Truncate string to max length"""
    if len(text) <= max_length:
        return text
    return text[:max_length - len(suffix)] + suffix

def merge_dicts(dict1: Dict, dict2: Dict, deep: bool = False) -> Dict:
    """
    Merge two dictionaries
    
    Args:
        dict1: First dictionary
        dict2: Second dictionary (overrides dict1)
        deep: Whether to do deep merge
    
    Returns:
        Merged dictionary
    """
    if not deep:
        return {**dict1, **dict2}
    
    result = dict1.copy()
    for key, value in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = merge_dicts(result[key], value, deep=True)
        else:
            result[key] = value
    
    return result

def get_nested_value(data: Dict, path: str, default: Any = None) -> Any:
    """
    Get nested dictionary value using dot notation
    
    Args:
        data: Dictionary to search
        path: Dot-separated path (e.g., "user.profile.name")
        default: Default value if path not found
    
    Returns:
        Value at path or default
    """
    keys = path.split('.')
    current = data
    
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
            if current is None:
                return default
        else:
            return default
    
    return current

def generate_random_password(length: int = 12) -> str:
    """Generate a secure random password"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def parse_bool(value: Any) -> bool:
    """Parse various representations to boolean"""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        return value.lower() in ('true', 'yes', '1', 'on', 'y', 't')
    return False

def to_camel_case(snake_str: str) -> str:
    """Convert snake_case to camelCase"""
    components = snake_str.split('_')
    return components[0] + ''.join(x.title() for x in components[1:])

def to_snake_case(camel_str: str) -> str:
    """Convert camelCase to snake_case"""
    pattern = re.compile(r'(?<!^)(?=[A-Z])')
    return pattern.sub('_', camel_str).lower()