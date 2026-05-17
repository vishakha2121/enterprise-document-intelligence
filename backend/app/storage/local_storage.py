"""
Local Storage Handler
File system based storage for local development and fallback
"""

import shutil
import logging
from pathlib import Path
from typing import Optional, BinaryIO, Dict, Any, List
import asyncio
from datetime import datetime
import aiofiles
import hashlib

from app.config import settings

logger = logging.getLogger(__name__)

class LocalStorage:
    """
    Local file system storage handler
    Used as primary storage for development and fallback for production
    """
    
    def __init__(self):
        """Initialize local storage"""
        self.base_path = settings.UPLOAD_DIR
        self.processed_path = settings.PROCESSED_DIR
        self.temp_path = settings.TEMP_DIR
        
        # Ensure directories exist
        self.base_path.mkdir(parents=True, exist_ok=True)
        self.processed_path.mkdir(parents=True, exist_ok=True)
        self.temp_path.mkdir(parents=True, exist_ok=True)
        
        logger.info(f"Local storage initialized at {self.base_path}")
    
    async def upload_file(
        self,
        file_data: bytes,
        key: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Save file to local storage
        
        Args:
            file_data: File content as bytes
            key: File path (relative to base directory)
            content_type: MIME type (ignored for local storage)
            metadata: Additional metadata (stored as .meta file)
        
        Returns:
            Upload result with path and URL
        """
        try:
            # Build full path
            file_path = self.base_path / key
            
            # Create parent directories if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write file asynchronously
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(file_data)
            
            # Save metadata if provided
            if metadata:
                meta_path = file_path.with_suffix(file_path.suffix + '.meta')
                import json
                async with aiofiles.open(meta_path, 'w') as f:
                    await f.write(json.dumps(metadata))
            
            # Calculate file hash
            file_hash = hashlib.sha256(file_data).hexdigest()
            
            return {
                "success": True,
                "key": str(key),
                "path": str(file_path),
                "url": f"/api/v1/documents/download/{key}",
                "size": len(file_data),
                "hash": file_hash
            }
        
        except Exception as e:
            logger.error(f"Local storage upload failed for {key}: {str(e)}")
            raise
    
    async def download_file(self, key: str) -> bytes:
        """
        Download file from local storage
        
        Args:
            key: File path (relative to base directory)
        
        Returns:
            File content as bytes
        """
        try:
            file_path = self.base_path / key
            
            if not file_path.exists():
                raise FileNotFoundError(f"File {key} not found")
            
            async with aiofiles.open(file_path, 'rb') as f:
                content = await f.read()
            
            return content
        
        except Exception as e:
            logger.error(f"Local storage download failed for {key}: {str(e)}")
            raise
    
    async def delete_file(self, key: str) -> bool:
        """
        Delete file from local storage
        
        Args:
            key: File path (relative to base directory)
        
        Returns:
            True if deleted successfully
        """
        try:
            file_path = self.base_path / key
            
            if file_path.exists():
                file_path.unlink()
            
            # Delete metadata file if exists
            meta_path = file_path.with_suffix(file_path.suffix + '.meta')
            if meta_path.exists():
                meta_path.unlink()
            
            return True
        
        except Exception as e:
            logger.error(f"Local storage delete failed for {key}: {str(e)}")
            return False
    
    async def file_exists(self, key: str) -> bool:
        """Check if file exists in local storage"""
        file_path = self.base_path / key
        return file_path.exists()
    
    async def get_file_metadata(self, key: str) -> Optional[Dict[str, Any]]:
        """Get file metadata"""
        try:
            file_path = self.base_path / key
            
            if not file_path.exists():
                return None
            
            stat = file_path.stat()
            
            metadata = {
                "size": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "path": str(file_path)
            }
            
            # Load custom metadata if exists
            meta_path = file_path.with_suffix(file_path.suffix + '.meta')
            if meta_path.exists():
                import json
                async with aiofiles.open(meta_path, 'r') as f:
                    content = await f.read()
                    custom_metadata = json.loads(content)
                    metadata["custom_metadata"] = custom_metadata
            
            return metadata
        
        except Exception as e:
            logger.error(f"Failed to get metadata for {key}: {str(e)}")
            return None
    
    async def list_files(
        self,
        prefix: str = "",
        max_files: int = 1000
    ) -> List[Dict[str, Any]]:
        """List files in local storage"""
        try:
            search_path = self.base_path / prefix if prefix else self.base_path
            
            files = []
            for file_path in search_path.rglob("*"):
                if file_path.is_file() and not file_path.name.endswith('.meta'):
                    stat = file_path.stat()
                    rel_path = file_path.relative_to(self.base_path)
                    
                    files.append({
                        "key": str(rel_path),
                        "size": stat.st_size,
                        "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat()
                    })
                    
                    if len(files) >= max_files:
                        break
            
            return files
        
        except Exception as e:
            logger.error(f"Failed to list files: {str(e)}")
            return []
    
    async def copy_file(self, source_key: str, destination_key: str) -> bool:
        """Copy file within local storage"""
        try:
            source_path = self.base_path / source_key
            dest_path = self.base_path / destination_key
            
            if not source_path.exists():
                return False
            
            # Create parent directories
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Copy file
            shutil.copy2(source_path, dest_path)
            
            # Copy metadata if exists
            source_meta = source_path.with_suffix(source_path.suffix + '.meta')
            if source_meta.exists():
                dest_meta = dest_path.with_suffix(dest_path.suffix + '.meta')
                shutil.copy2(source_meta, dest_meta)
            
            return True
        
        except Exception as e:
            logger.error(f"Copy failed from {source_key} to {destination_key}: {str(e)}")
            return False
    
    async def move_file(self, source_key: str, destination_key: str) -> bool:
        """Move file within local storage"""
        try:
            source_path = self.base_path / source_key
            dest_path = self.base_path / destination_key
            
            if not source_path.exists():
                return False
            
            # Create parent directories
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Move file
            shutil.move(str(source_path), str(dest_path))
            
            # Move metadata if exists
            source_meta = source_path.with_suffix(source_path.suffix + '.meta')
            if source_meta.exists():
                dest_meta = dest_path.with_suffix(dest_path.suffix + '.meta')
                shutil.move(str(source_meta), str(dest_meta))
            
            return True
        
        except Exception as e:
            logger.error(f"Move failed from {source_key} to {destination_key}: {str(e)}")
            return False
    
    async def get_presigned_url(
        self,
        key: str,
        expiration_seconds: int = 3600,
        method: str = 'get_object'
    ) -> Optional[str]:
        """
        Generate URL for temporary access (local storage returns direct path)
        """
        # For local storage, return direct file path with timestamp to avoid cache
        file_path = self.base_path / key
        if not file_path.exists():
            return None
        
        # Return URL with timestamp for cache busting
        timestamp = datetime.now().timestamp()
        return f"/api/v1/documents/download/{key}?t={timestamp}"
    
    async def save_temp_file(self, file_data: bytes, filename: str) -> Path:
        """Save temporary file for processing"""
        try:
            temp_file = self.temp_path / filename
            async with aiofiles.open(temp_file, 'wb') as f:
                await f.write(file_data)
            return temp_file
        except Exception as e:
            logger.error(f"Failed to save temp file: {str(e)}")
            raise
    
    async def delete_temp_file(self, filename: str) -> bool:
        """Delete temporary file"""
        try:
            temp_file = self.temp_path / filename
            if temp_file.exists():
                temp_file.unlink()
            return True
        except Exception as e:
            logger.error(f"Failed to delete temp file: {str(e)}")
            return False
    
    async def cleanup_temp_files(self, max_age_hours: int = 24):
        """Clean up old temporary files"""
        try:
            cutoff_time = datetime.now().timestamp() - (max_age_hours * 3600)
            
            for temp_file in self.temp_path.glob("*"):
                if temp_file.stat().st_mtime < cutoff_time:
                    temp_file.unlink()
                    logger.debug(f"Cleaned up temp file: {temp_file.name}")
        
        except Exception as e:
            logger.error(f"Temp file cleanup failed: {str(e)}")
    
    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        try:
            total_size = 0
            total_files = 0
            
            for file_path in self.base_path.rglob("*"):
                if file_path.is_file() and not file_path.name.endswith('.meta'):
                    total_size += file_path.stat().st_size
                    total_files += 1
            
            return {
                "total_files": total_files,
                "total_size_bytes": total_size,
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "base_path": str(self.base_path),
                "temp_path": str(self.temp_path)
            }
        
        except Exception as e:
            logger.error(f"Failed to get storage stats: {str(e)}")
            return {}
    
    def is_available(self) -> bool:
        """Check if local storage is available"""
        return self.base_path.exists() and self.base_path.is_dir()
    
    async def health_check(self) -> Dict[str, Any]:
        """Check local storage health"""
        try:
            # Test write operation
            test_file = self.temp_path / ".health_check"
            async with aiofiles.open(test_file, 'w') as f:
                await f.write("test")
            test_file.unlink()
            
            return {
                "available": True,
                "base_path": str(self.base_path),
                "writable": True,
                "free_space_mb": shutil.disk_usage(self.base_path).free / (1024 * 1024)
            }
        except Exception as e:
            return {
                "available": False,
                "error": str(e)
            }