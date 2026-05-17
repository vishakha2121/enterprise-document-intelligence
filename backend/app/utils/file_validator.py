"""
File Validator
Validates file types, sizes, and content for security
"""

import magic
import logging
from pathlib import Path
from typing import Tuple, Optional, List, Dict, Any
import imghdr
import PyPDF2
import io

from app.config import settings

logger = logging.getLogger(__name__)

class FileValidator:
    """
    Validates uploaded files for security and compatibility
    Checks file type, size, MIME type, and content integrity
    """
    
    def __init__(self):
        """Initialize file validator with configuration"""
        self.max_size = settings.MAX_FILE_SIZE
        self.allowed_extensions = settings.ALLOWED_EXTENSIONS
        self.allowed_mime_types = settings.ALLOWED_MIME_TYPES
        
        # Initialize magic for MIME detection
        self.magic = magic.Magic(mime=True)
    
    def validate(
        self,
        filename: str,
        file_size: Optional[int] = None,
        file_content: Optional[bytes] = None
    ) -> Dict[str, Any]:
        """
        Validate file based on name, size, and content
        
        Args:
            filename: Original filename
            file_size: File size in bytes
            file_content: File content bytes for deeper validation
        
        Returns:
            Validation result with status and message
        """
        # Check filename
        filename_valid, filename_error = self._validate_filename(filename)
        if not filename_valid:
            return {
                "is_valid": False,
                "error": filename_error,
                "error_code": "INVALID_FILENAME"
            }
        
        # Check extension
        extension_valid, extension_error = self._validate_extension(filename)
        if not extension_valid:
            return {
                "is_valid": False,
                "error": extension_error,
                "error_code": "INVALID_EXTENSION"
            }
        
        # Check file size
        if file_size is not None:
            size_valid, size_error = self._validate_size(file_size)
            if not size_valid:
                return {
                    "is_valid": False,
                    "error": size_error,
                    "error_code": "FILE_TOO_LARGE"
                }
        
        # Check MIME type and content
        if file_content is not None:
            mime_valid, mime_error, detected_mime = self._validate_mime_type(file_content)
            if not mime_valid:
                return {
                    "is_valid": False,
                    "error": mime_error,
                    "error_code": "INVALID_MIME_TYPE",
                    "detected_mime": detected_mime
                }
            
            # Deep validation for specific file types
            content_valid, content_error = self._deep_validate_content(file_content, detected_mime)
            if not content_valid:
                return {
                    "is_valid": False,
                    "error": content_error,
                    "error_code": "CORRUPTED_FILE"
                }
        
        return {
            "is_valid": True,
            "message": "File is valid",
            "file_size": file_size,
            "extension": Path(filename).suffix.lower()
        }
    
    def _validate_filename(self, filename: str) -> Tuple[bool, str]:
        """Validate filename for security"""
        if not filename:
            return False, "Filename is empty"
        
        # Check for path traversal
        if ".." in filename or "/" in filename or "\\" in filename:
            return False, "Invalid filename contains path traversal"
        
        # Check length
        if len(filename) > 255:
            return False, "Filename too long (max 255 characters)"
        
        # Check for suspicious characters
        suspicious_chars = [';', '|', '&', '$', '`', '(', ')', '<', '>']
        for char in suspicious_chars:
            if char in filename:
                return False, f"Invalid character in filename: {char}"
        
        return True, ""
    
    def _validate_extension(self, filename: str) -> Tuple[bool, str]:
        """Validate file extension"""
        ext = Path(filename).suffix.lower()
        
        if not ext:
            return False, "File has no extension"
        
        if ext not in self.allowed_extensions:
            return False, f"File extension '{ext}' not allowed. Allowed: {', '.join(self.allowed_extensions)}"
        
        return True, ""
    
    def _validate_size(self, file_size: int) -> Tuple[bool, str]:
        """Validate file size"""
        if file_size > self.max_size:
            max_size_mb = self.max_size / (1024 * 1024)
            file_size_mb = file_size / (1024 * 1024)
            return False, f"File size ({file_size_mb:.2f}MB) exceeds maximum ({max_size_mb:.2f}MB)"
        
        if file_size == 0:
            return False, "File is empty"
        
        return True, ""
    
    def _validate_mime_type(self, file_content: bytes) -> Tuple[bool, str, Optional[str]]:
        """Validate MIME type using magic numbers"""
        try:
            detected_mime = self.magic.from_buffer(file_content[:1024])
            
            if detected_mime not in self.allowed_mime_types:
                return False, f"MIME type '{detected_mime}' not allowed", detected_mime
            
            return True, "", detected_mime
        
        except Exception as e:
            logger.error(f"MIME detection failed: {str(e)}")
            return False, "Could not determine file type", None
    
    def _deep_validate_content(self, file_content: bytes, mime_type: str) -> Tuple[bool, str]:
        """Deep validation for specific file types"""
        try:
            if "pdf" in mime_type:
                return self._validate_pdf(file_content)
            elif "image" in mime_type:
                return self._validate_image(file_content)
            else:
                return True, ""
        
        except Exception as e:
            logger.error(f"Deep validation failed: {str(e)}")
            return False, f"File validation failed: {str(e)}"
    
    def _validate_pdf(self, file_content: bytes) -> Tuple[bool, str]:
        """Validate PDF file integrity"""
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
            
            # Check if PDF is encrypted
            if pdf_reader.is_encrypted:
                return False, "Encrypted PDF files are not supported"
            
            # Check number of pages
            if len(pdf_reader.pages) > 500:
                return False, "PDF has too many pages (max 500)"
            
            # Check for JavaScript or embedded files
            if hasattr(pdf_reader, 'metadata'):
                metadata = pdf_reader.metadata
                if metadata and '/JS' in str(metadata):
                    return False, "PDF contains JavaScript which is not allowed"
            
            return True, ""
        
        except PyPDF2.PdfReadError as e:
            return False, f"PDF is corrupted or invalid: {str(e)}"
        except Exception as e:
            return False, f"PDF validation failed: {str(e)}"
    
    def _validate_image(self, file_content: bytes) -> Tuple[bool, str]:
        """Validate image file integrity"""
        try:
            # Detect image type
            image_type = imghdr.what(None, file_content)
            
            if not image_type:
                return False, "Invalid or corrupted image file"
            
            # Check image dimensions (basic check)
            from PIL import Image
            import io
            
            img = Image.open(io.BytesIO(file_content))
            width, height = img.size
            
            # Max dimensions
            if width > 10000 or height > 10000:
                return False, f"Image dimensions too large: {width}x{height} (max 10000x10000)"
            
            return True, ""
        
        except Exception as e:
            return False, f"Image validation failed: {str(e)}"
    
    def validate_document_content(self, file_content: bytes) -> Dict[str, Any]:
        """
        Extract and validate document content
        Returns content preview and basic validation
        """
        result = {
            "is_valid": True,
            "content_preview": "",
            "page_count": 0,
            "text_length": 0
        }
        
        try:
            mime_type = self.magic.from_buffer(file_content[:1024])
            
            if "pdf" in mime_type:
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_content))
                result["page_count"] = len(pdf_reader.pages)
                
                # Extract first page preview
                if result["page_count"] > 0:
                    first_page = pdf_reader.pages[0]
                    text = first_page.extract_text()
                    result["content_preview"] = text[:500] if text else ""
                    result["text_length"] = len(text) if text else 0
            
            elif "text" in mime_type:
                text = file_content.decode('utf-8', errors='ignore')
                result["content_preview"] = text[:500]
                result["text_length"] = len(text)
        
        except Exception as e:
            logger.error(f"Content extraction failed: {str(e)}")
            result["is_valid"] = False
            result["error"] = str(e)
        
        return result
    
    def get_file_info(self, filename: str, file_size: int) -> Dict[str, Any]:
        """Get basic file information without content validation"""
        ext = Path(filename).suffix.lower()
        
        return {
            "filename": filename,
            "extension": ext,
            "size_bytes": file_size,
            "size_mb": round(file_size / (1024 * 1024), 2),
            "is_valid_extension": ext in self.allowed_extensions,
            "is_valid_size": file_size <= self.max_size
        }