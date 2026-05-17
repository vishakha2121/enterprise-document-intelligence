"""
Tests for Document API Routes
"""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi import status
from io import BytesIO


class TestDocumentAPI:
    """Test cases for document management endpoints"""
    
    @pytest.mark.asyncio
    async def test_upload_document_success(self, client, auth_headers, sample_pdf_content):
        """Test successful document upload"""
        files = {
            "file": ("test_invoice.pdf", sample_pdf_content, "application/pdf")
        }
        
        response = client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "document_id" in data["data"]
        assert data["data"]["status"] == "uploaded"
    
    @pytest.mark.asyncio
    async def test_upload_document_invalid_type(self, client, auth_headers):
        """Test upload with invalid file type"""
        files = {
            "file": ("test.txt", b"invalid content", "text/plain")
        }
        
        response = client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        data = response.json()
        assert data["success"] is False
    
    @pytest.mark.asyncio
    async def test_upload_document_too_large(self, client, auth_headers):
        """Test upload with file too large"""
        large_content = b"x" * (11 * 1024 * 1024)  # 11MB
        files = {
            "file": ("large.pdf", large_content, "application/pdf")
        }
        
        response = client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
    
    @pytest.mark.asyncio
    async def test_get_document_success(self, client, auth_headers):
        """Test get document by ID"""
        # First upload a document
        files = {
            "file": ("test.pdf", b"test content", "application/pdf")
        }
        upload_response = client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=auth_headers
        )
        doc_id = upload_response.json()["data"]["document_id"]
        
        # Then retrieve it
        response = client.get(
            f"/api/v1/documents/{doc_id}",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["id"] == doc_id
    
    @pytest.mark.asyncio
    async def test_get_document_not_found(self, client, auth_headers):
        """Test get non-existent document"""
        response = client.get(
            "/api/v1/documents/99999",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    @pytest.mark.asyncio
    async def test_list_documents(self, client, auth_headers):
        """Test list documents with pagination"""
        response = client.get(
            "/api/v1/documents/?page=1&page_size=10",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "items" in data["data"]
        assert "total" in data["data"]
    
    @pytest.mark.asyncio
    async def test_list_documents_with_filters(self, client, auth_headers):
        """Test list documents with filters"""
        response = client.get(
            "/api/v1/documents/?document_type=invoice&status=uploaded",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
    
    @pytest.mark.asyncio
    async def test_update_document(self, client, auth_headers):
        """Test update document metadata"""
        # Upload document first
        files = {
            "file": ("test.pdf", b"test content", "application/pdf")
        }
        upload_response = client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=auth_headers
        )
        doc_id = upload_response.json()["data"]["document_id"]
        
        # Update document
        update_data = {
            "title": "Updated Title",
            "description": "Updated description",
            "tags": ["test", "updated"]
        }
        
        response = client.put(
            f"/api/v1/documents/{doc_id}",
            json=update_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert data["data"]["title"] == "Updated Title"
    
    @pytest.mark.asyncio
    async def test_delete_document(self, client, auth_headers):
        """Test delete document"""
        # Upload document first
        files = {
            "file": ("test.pdf", b"test content", "application/pdf")
        }
        upload_response = client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=auth_headers
        )
        doc_id = upload_response.json()["data"]["document_id"]
        
        # Delete document
        response = client.delete(
            f"/api/v1/documents/{doc_id}",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        
        # Verify document is deleted
        get_response = client.get(
            f"/api/v1/documents/{doc_id}",
            headers=auth_headers
        )
        assert get_response.status_code == status.HTTP_404_NOT_FOUND
    
    @pytest.mark.asyncio
    async def test_download_document(self, client, auth_headers, sample_pdf_content):
        """Test document download"""
        # Upload document
        files = {
            "file": ("test.pdf", sample_pdf_content, "application/pdf")
        }
        upload_response = client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=auth_headers
        )
        doc_id = upload_response.json()["data"]["document_id"]
        
        # Download document
        response = client.get(
            f"/api/v1/documents/{doc_id}/download",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.headers["content-type"] == "application/octet-stream"
    
    @pytest.mark.asyncio
    async def test_get_document_stats(self, client, auth_headers):
        """Test get document statistics"""
        response = client.get(
            "/api/v1/documents/stats/summary",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "total_documents" in data["data"]


class TestBatchUploadAPI:
    """Test cases for batch upload endpoints"""
    
    @pytest.mark.asyncio
    async def test_batch_upload(self, client, auth_headers, sample_pdf_content):
        """Test batch upload of multiple documents"""
        files = [
            ("files", ("invoice1.pdf", sample_pdf_content, "application/pdf")),
            ("files", ("invoice2.pdf", sample_pdf_content, "application/pdf")),
            ("files", ("invoice3.pdf", sample_pdf_content, "application/pdf")),
        ]
        
        response = client.post(
            "/api/v1/documents/upload-batch",
            files=files,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]) == 3