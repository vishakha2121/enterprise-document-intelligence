"""
AWS S3 Client
Cloud storage operations using boto3
"""

import boto3
import logging
from botocore.exceptions import ClientError, NoCredentialsError
from typing import Optional, BinaryIO, Dict, Any, List
from pathlib import Path
import io
import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta

from app.config import settings

logger = logging.getLogger(__name__)

class S3Client:
    """
    AWS S3 client for cloud storage operations
    Supports upload, download, delete, and presigned URLs
    """
    
    def __init__(self):
        """Initialize S3 client"""
        self.bucket_name = settings.AWS_S3_BUCKET
        self.region = settings.AWS_REGION
        self.is_configured = False
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Check if AWS credentials are configured
        if settings.AWS_ACCESS_KEY_ID and settings.AWS_SECRET_ACCESS_KEY:
            try:
                self.s3_client = boto3.client(
                    's3',
                    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
                    region_name=self.region
                )
                self.is_configured = True
                logger.info(f"S3 client initialized for bucket: {self.bucket_name}")
            except Exception as e:
                logger.error(f"Failed to initialize S3 client: {str(e)}")
                self.is_configured = False
        else:
            logger.warning("AWS credentials not configured. S3 storage disabled.")
    
    async def upload_file(
        self,
        file_data: bytes,
        key: str,
        content_type: str = "application/octet-stream",
        metadata: Optional[Dict[str, str]] = None
    ) -> Dict[str, Any]:
        """
        Upload file to S3
        
        Args:
            file_data: File content as bytes
            key: S3 object key (path)
            content_type: MIME type of the file
            metadata: Additional metadata for the object
        
        Returns:
            Upload result with key and URL
        """
        if not self.is_configured:
            raise ValueError("S3 is not configured")
        
        try:
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                self._upload_file_sync,
                file_data,
                key,
                content_type,
                metadata
            )
            return result
        
        except Exception as e:
            logger.error(f"S3 upload failed for {key}: {str(e)}")
            raise
    
    def _upload_file_sync(
        self,
        file_data: bytes,
        key: str,
        content_type: str,
        metadata: Optional[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Synchronous upload implementation"""
        try:
            extra_args = {
                'ContentType': content_type,
                'ACL': 'private'
            }
            
            if metadata:
                extra_args['Metadata'] = metadata
            
            self.s3_client.upload_fileobj(
                io.BytesIO(file_data),
                self.bucket_name,
                key,
                ExtraArgs=extra_args
            )
            
            # Generate object URL
            url = f"https://{self.bucket_name}.s3.{self.region}.amazonaws.com/{key}"
            
            return {
                "success": True,
                "key": key,
                "url": url,
                "bucket": self.bucket_name,
                "region": self.region,
                "size": len(file_data)
            }
        
        except ClientError as e:
            logger.error(f"S3 client error: {str(e)}")
            raise
        except Exception as e:
            logger.error(f"S3 upload error: {str(e)}")
            raise
    
    async def download_file(self, key: str) -> bytes:
        """
        Download file from S3
        
        Args:
            key: S3 object key
        
        Returns:
            File content as bytes
        """
        if not self.is_configured:
            raise ValueError("S3 is not configured")
        
        try:
            loop = asyncio.get_event_loop()
            content = await loop.run_in_executor(
                self.executor,
                self._download_file_sync,
                key
            )
            return content
        
        except Exception as e:
            logger.error(f"S3 download failed for {key}: {str(e)}")
            raise
    
    def _download_file_sync(self, key: str) -> bytes:
        """Synchronous download implementation"""
        try:
            buffer = io.BytesIO()
            self.s3_client.download_fileobj(self.bucket_name, key, buffer)
            buffer.seek(0)
            return buffer.read()
        
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                raise FileNotFoundError(f"File {key} not found in S3")
            raise
    
    async def delete_file(self, key: str) -> bool:
        """
        Delete file from S3
        
        Args:
            key: S3 object key
        
        Returns:
            True if deleted successfully
        """
        if not self.is_configured:
            raise ValueError("S3 is not configured")
        
        try:
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                self.executor,
                self._delete_file_sync,
                key
            )
            return result
        
        except Exception as e:
            logger.error(f"S3 delete failed for {key}: {str(e)}")
            return False
    
    def _delete_file_sync(self, key: str) -> bool:
        """Synchronous delete implementation"""
        try:
            self.s3_client.delete_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError as e:
            logger.error(f"S3 delete error: {str(e)}")
            return False
    
    async def get_presigned_url(
        self,
        key: str,
        expiration_seconds: int = 3600,
        method: str = 'get_object'
    ) -> Optional[str]:
        """
        Generate presigned URL for temporary access
        
        Args:
            key: S3 object key
            expiration_seconds: URL expiration time in seconds
            method: HTTP method (get_object, put_object)
        
        Returns:
            Presigned URL or None if failed
        """
        if not self.is_configured:
            return None
        
        try:
            loop = asyncio.get_event_loop()
            url = await loop.run_in_executor(
                self.executor,
                self._generate_presigned_url_sync,
                key,
                expiration_seconds,
                method
            )
            return url
        
        except Exception as e:
            logger.error(f"Failed to generate presigned URL for {key}: {str(e)}")
            return None
    
    def _generate_presigned_url_sync(
        self,
        key: str,
        expiration_seconds: int,
        method: str
    ) -> Optional[str]:
        """Synchronous presigned URL generation"""
        try:
            url = self.s3_client.generate_presigned_url(
                ClientMethod=method,
                Params={'Bucket': self.bucket_name, 'Key': key},
                ExpiresIn=expiration_seconds
            )
            return url
        except ClientError as e:
            logger.error(f"Presigned URL error: {str(e)}")
            return None
    
    async def file_exists(self, key: str) -> bool:
        """Check if file exists in S3"""
        if not self.is_configured:
            return False
        
        try:
            loop = asyncio.get_event_loop()
            exists = await loop.run_in_executor(
                self.executor,
                self._file_exists_sync,
                key
            )
            return exists
        except Exception:
            return False
    
    def _file_exists_sync(self, key: str) -> bool:
        """Synchronous existence check"""
        try:
            self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return True
        except ClientError:
            return False
    
    async def list_files(
        self,
        prefix: str = "",
        max_keys: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        List files in S3 bucket
        
        Args:
            prefix: Key prefix to filter
            max_keys: Maximum number of keys to return
        
        Returns:
            List of file metadata
        """
        if not self.is_configured:
            return []
        
        try:
            loop = asyncio.get_event_loop()
            files = await loop.run_in_executor(
                self.executor,
                self._list_files_sync,
                prefix,
                max_keys
            )
            return files
        except Exception as e:
            logger.error(f"Failed to list S3 files: {str(e)}")
            return []
    
    def _list_files_sync(self, prefix: str, max_keys: int) -> List[Dict[str, Any]]:
        """Synchronous list implementation"""
        try:
            response = self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                Prefix=prefix,
                MaxKeys=max_keys
            )
            
            files = []
            if 'Contents' in response:
                for obj in response['Contents']:
                    files.append({
                        "key": obj['Key'],
                        "size": obj['Size'],
                        "last_modified": obj['LastModified'].isoformat(),
                        "etag": obj['ETag'].strip('"')
                    })
            
            return files
        
        except ClientError as e:
            logger.error(f"List files error: {str(e)}")
            return []
    
    async def copy_file(self, source_key: str, destination_key: str) -> bool:
        """Copy file within S3 bucket"""
        if not self.is_configured:
            return False
        
        try:
            copy_source = {'Bucket': self.bucket_name, 'Key': source_key}
            
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                self.executor,
                self.s3_client.copy_object,
                copy_source,
                self.bucket_name,
                destination_key
            )
            return True
        
        except Exception as e:
            logger.error(f"Copy failed from {source_key} to {destination_key}: {str(e)}")
            return False
    
    async def get_file_metadata(self, key: str) -> Optional[Dict[str, Any]]:
        """Get file metadata from S3"""
        if not self.is_configured:
            return None
        
        try:
            loop = asyncio.get_event_loop()
            metadata = await loop.run_in_executor(
                self.executor,
                self._get_metadata_sync,
                key
            )
            return metadata
        except Exception:
            return None
    
    def _get_metadata_sync(self, key: str) -> Optional[Dict[str, Any]]:
        """Synchronous metadata retrieval"""
        try:
            response = self.s3_client.head_object(Bucket=self.bucket_name, Key=key)
            return {
                "size": response['ContentLength'],
                "content_type": response.get('ContentType'),
                "last_modified": response['LastModified'].isoformat(),
                "etag": response['ETag'].strip('"'),
                "metadata": response.get('Metadata', {})
            }
        except ClientError:
            return None
    
    async def upload_large_file(
        self,
        file_path: Path,
        key: str,
        callback: Optional[callable] = None
    ) -> Dict[str, Any]:
        """
        Upload large file using multipart upload
        
        Args:
            file_path: Local file path
            key: S3 object key
            callback: Progress callback function
        """
        if not self.is_configured:
            raise ValueError("S3 is not configured")
        
        try:
            # Get file size
            file_size = file_path.stat().st_size
            part_size = 5 * 1024 * 1024  # 5 MB parts
            parts = []
            
            # Create multipart upload
            mpu = self.s3_client.create_multipart_upload(
                Bucket=self.bucket_name,
                Key=key
            )
            upload_id = mpu['UploadId']
            
            # Upload parts
            with open(file_path, 'rb') as f:
                part_number = 1
                while True:
                    data = f.read(part_size)
                    if not data:
                        break
                    
                    part = self.s3_client.upload_part(
                        Bucket=self.bucket_name,
                        Key=key,
                        PartNumber=part_number,
                        UploadId=upload_id,
                        Body=data
                    )
                    parts.append({
                        'PartNumber': part_number,
                        'ETag': part['ETag']
                    })
                    
                    if callback:
                        progress = (part_number * part_size) / file_size * 100
                        callback(progress)
                    
                    part_number += 1
            
            # Complete upload
            self.s3_client.complete_multipart_upload(
                Bucket=self.bucket_name,
                Key=key,
                UploadId=upload_id,
                MultipartUpload={'Parts': parts}
            )
            
            return {
                "success": True,
                "key": key,
                "size": file_size,
                "parts": len(parts)
            }
        
        except Exception as e:
            # Abort multipart upload on failure
            if 'upload_id' in locals():
                self.s3_client.abort_multipart_upload(
                    Bucket=self.bucket_name,
                    Key=key,
                    UploadId=upload_id
                )
            logger.error(f"Large file upload failed: {str(e)}")
            raise
    
    def is_available(self) -> bool:
        """Check if S3 storage is available"""
        return self.is_configured
    
    async def health_check(self) -> Dict[str, Any]:
        """Check S3 service health"""
        if not self.is_configured:
            return {"available": False, "message": "S3 not configured"}
        
        try:
            # Try to list bucket (limited to 1 object)
            self.s3_client.list_objects_v2(
                Bucket=self.bucket_name,
                MaxKeys=1
            )
            return {
                "available": True,
                "bucket": self.bucket_name,
                "region": self.region
            }
        except Exception as e:
            return {
                "available": False,
                "error": str(e)
            }