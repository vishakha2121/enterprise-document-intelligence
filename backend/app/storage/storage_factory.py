"""
Storage Factory
Abstraction for switching between local and cloud storage
"""

import logging
from enum import Enum
from typing import Optional, Dict, Any, Union
from pathlib import Path

from app.config import settings
from app.storage.local_storage import LocalStorage
from app.storage.s3_client import S3Client

logger = logging.getLogger(__name__)

class StorageType(str, Enum):
    """Storage provider types"""
    LOCAL = "local"
    S3 = "s3"
    AUTO = "auto"

class StorageFactory:
    """
    Storage factory for abstracting storage operations
    Automatically chooses between local and S3 based on configuration
    """
    
    def __init__(self):
        """Initialize storage factory"""
        self.local_storage = LocalStorage()
        self.s3_storage = S3Client()
        
        # Determine primary storage
        self.use_s3 = settings.USE_S3_STORAGE and self.s3_storage.is_available()
        self.primary_storage = self.s3_storage if self.use_s3 else self.local_storage
        
        logger.info(f"Storage factory initialized. Primary storage: {'S3' if self.use_s3 else 'Local'}")
    
    async def upload_file(
        self,
        file_data: bytes,
        key: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None,
        storage_type: StorageType = StorageType.AUTO
    ) -> Dict[str, Any]:
        """
        Upload file using appropriate storage
        
        Args:
            file_data: File content as bytes
            key: File path/key
            content_type: MIME type
            metadata: Additional metadata
            storage_type: Force specific storage type
        
        Returns:
            Upload result
        """
        storage = self._get_storage(storage_type)
        return await storage.upload_file(file_data, key, content_type, metadata)
    
    async def download_file(
        self,
        key: str,
        storage_type: StorageType = StorageType.AUTO
    ) -> bytes:
        """Download file from storage"""
        storage = self._get_storage(storage_type)
        return await storage.download_file(key)
    
    async def delete_file(
        self,
        key: str,
        storage_type: StorageType = StorageType.AUTO
    ) -> bool:
        """Delete file from storage"""
        storage = self._get_storage(storage_type)
        return await storage.delete_file(key)
    
    async def file_exists(
        self,
        key: str,
        storage_type: StorageType = StorageType.AUTO
    ) -> bool:
        """Check if file exists in storage"""
        storage = self._get_storage(storage_type)
        return await storage.file_exists(key)
    
    async def get_file_metadata(
        self,
        key: str,
        storage_type: StorageType = StorageType.AUTO
    ) -> Optional[Dict[str, Any]]:
        """Get file metadata"""
        storage = self._get_storage(storage_type)
        return await storage.get_file_metadata(key)
    
    async def get_presigned_url(
        self,
        key: str,
        expiration_seconds: int = 3600,
        method: str = 'get_object',
        storage_type: StorageType = StorageType.AUTO
    ) -> Optional[str]:
        """Generate presigned URL for temporary access"""
        storage = self._get_storage(storage_type)
        return await storage.get_presigned_url(key, expiration_seconds, method)
    
    async def list_files(
        self,
        prefix: str = "",
        max_files: int = 1000,
        storage_type: StorageType = StorageType.AUTO
    ) -> list:
        """List files in storage"""
        storage = self._get_storage(storage_type)
        return await storage.list_files(prefix, max_files)
    
    async def copy_file(
        self,
        source_key: str,
        destination_key: str,
        storage_type: StorageType = StorageType.AUTO
    ) -> bool:
        """Copy file within storage"""
        storage = self._get_storage(storage_type)
        return await storage.copy_file(source_key, destination_key)
    
    def _get_storage(self, storage_type: StorageType):
        """Get storage instance based on type"""
        if storage_type == StorageType.LOCAL:
            return self.local_storage
        elif storage_type == StorageType.S3:
            if not self.s3_storage.is_available():
                logger.warning("S3 requested but not available, falling back to local")
                return self.local_storage
            return self.s3_storage
        else:  # AUTO
            return self.primary_storage
    
    async def upload_with_fallback(
        self,
        file_data: bytes,
        key: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Upload with automatic fallback
        Tries primary storage, falls back to local if fails
        """
        try:
            # Try primary storage
            result = await self.primary_storage.upload_file(
                file_data, key, content_type, metadata
            )
            return result
        
        except Exception as e:
            logger.error(f"Primary storage upload failed: {str(e)}")
            
            # Fallback to local storage
            if self.primary_storage != self.local_storage:
                logger.warning(f"Falling back to local storage for {key}")
                result = await self.local_storage.upload_file(
                    file_data, key, content_type, metadata
                )
                result["fallback_used"] = True
                return result
            else:
                raise
    
    async def sync_to_s3(self, key: str) -> bool:
        """Sync a file from local to S3"""
        if not self.s3_storage.is_available():
            return False
        
        try:
            # Check if file exists locally
            if not await self.local_storage.file_exists(key):
                return False
            
            # Download from local
            file_data = await self.local_storage.download_file(key)
            
            # Upload to S3
            metadata = await self.local_storage.get_file_metadata(key)
            await self.s3_storage.upload_file(
                file_data, key, 
                metadata=metadata.get("custom_metadata") if metadata else None
            )
            
            logger.info(f"Synced {key} to S3")
            return True
        
        except Exception as e:
            logger.error(f"Sync to S3 failed for {key}: {str(e)}")
            return False
    
    async def get_primary_storage_type(self) -> str:
        """Get current primary storage type"""
        return "s3" if self.use_s3 else "local"
    
    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics"""
        stats = {
            "primary_storage": await self.get_primary_storage_type(),
            "local": await self.local_storage.get_storage_stats(),
            "s3_available": self.s3_storage.is_available()
        }
        
        if self.s3_storage.is_available():
            stats["s3"] = {
                "bucket": settings.AWS_S3_BUCKET,
                "region": settings.AWS_REGION
            }
        
        return stats
    
    async def health_check(self) -> Dict[str, Any]:
        """Check health of all storage backends"""
        return {
            "primary_storage": await self.get_primary_storage_type(),
            "local": await self.local_storage.health_check(),
            "s3": await self.s3_storage.health_check() if self.s3_storage.is_available() else {"available": False}
        }
    
    async def migrate_to_s3(self, prefix: str = "") -> Dict[str, Any]:
        """
        Migrate files from local to S3
        
        Args:
            prefix: Only migrate files with this prefix
        
        Returns:
            Migration results
        """
        if not self.s3_storage.is_available():
            return {"success": False, "error": "S3 not available"}
        
        files = await self.local_storage.list_files(prefix)
        results = {
            "total": len(files),
            "successful": 0,
            "failed": 0,
            "failed_files": []
        }
        
        for file_info in files:
            key = file_info["key"]
            success = await self.sync_to_s3(key)
            
            if success:
                results["successful"] += 1
            else:
                results["failed"] += 1
                results["failed_files"].append(key)
        
        logger.info(f"Migration complete: {results['successful']}/{results['total']} files synced to S3")
        return results