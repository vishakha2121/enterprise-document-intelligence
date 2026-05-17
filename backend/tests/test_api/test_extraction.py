"""
Tests for Extraction API Routes
"""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi import status


class TestExtractionAPI:
    """Test cases for extraction endpoints"""
    
    @pytest.mark.asyncio
    async def test_extract_document_data(self, client, auth_headers, sample_pdf_content):
        """Test document data extraction"""
        # First upload a document
        files = {
            "file": ("invoice.pdf", sample_pdf_content, "application/pdf")
        }
        upload_response = client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=auth_headers
        )
        doc_id = upload_response.json()["data"]["document_id"]
        
        # Extract data
        response = client.post(
            f"/api/v1/extraction/extract/{doc_id}",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "extracted_data" in data["data"]
    
    @pytest.mark.asyncio
    async def test_extract_with_specific_fields(self, client, auth_headers, sample_pdf_content):
        """Test extraction with specific fields"""
        # Upload document
        files = {
            "file": ("invoice.pdf", sample_pdf_content, "application/pdf")
        }
        upload_response = client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=auth_headers
        )
        doc_id = upload_response.json()["data"]["document_id"]
        
        # Extract specific fields
        request_data = {
            "fields": ["invoice_number", "total_amount", "date"],
            "extraction_type": "specific_fields"
        }
        
        response = client.post(
            f"/api/v1/extraction/extract/{doc_id}",
            json=request_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
    
    @pytest.mark.asyncio
    async def test_get_extractions_by_document(self, client, auth_headers, sample_pdf_content):
        """Test get all extractions for a document"""
        # Upload and extract
        files = {
            "file": ("invoice.pdf", sample_pdf_content, "application/pdf")
        }
        upload_response = client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=auth_headers
        )
        doc_id = upload_response.json()["data"]["document_id"]
        
        # Perform extraction
        client.post(f"/api/v1/extraction/extract/{doc_id}", headers=auth_headers)
        
        # Get extractions
        response = client.get(
            f"/api/v1/extraction/extractions/{doc_id}",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
    
    @pytest.mark.asyncio
    async def test_export_extraction(self, client, auth_headers, sample_pdf_content):
        """Test export extraction data"""
        # Upload and extract
        files = {
            "file": ("invoice.pdf", sample_pdf_content, "application/pdf")
        }
        upload_response = client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=auth_headers
        )
        doc_id = upload_response.json()["data"]["document_id"]
        
        extraction_response = client.post(
            f"/api/v1/extraction/extract/{doc_id}",
            headers=auth_headers
        )
        extraction_id = extraction_response.json()["data"]["id"]
        
        # Export
        export_data = {
            "format": "json",
            "include_metadata": True
        }
        
        response = client.post(
            f"/api/v1/extraction/export/{extraction_id}",
            json=export_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "download_url" in data["data"]
    
    @pytest.mark.asyncio
    async def test_get_supported_fields(self, client, auth_headers):
        """Test get supported extraction fields"""
        response = client.get(
            "/api/v1/extraction/fields/supported",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "document_types" in data["data"]
        assert "fields_by_type" in data["data"]
    
    @pytest.mark.asyncio
    async def test_batch_extraction(self, client, auth_headers, sample_pdf_content):
        """Test batch extraction for multiple documents"""
        # Upload multiple documents
        doc_ids = []
        for i in range(3):
            files = {
                "file": (f"invoice_{i}.pdf", sample_pdf_content, "application/pdf")
            }
            response = client.post(
                "/api/v1/documents/upload",
                files=files,
                headers=auth_headers
            )
            doc_ids.append(response.json()["data"]["document_id"])
        
        # Batch extract
        response = client.post(
            "/api/v1/extraction/batch-extract",
            json=doc_ids,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "task_id" in data["data"]


class TestExtractionValidation:
    """Test cases for extraction validation"""
    
    @pytest.mark.asyncio
    async def test_validate_extraction(self, client, auth_headers, sample_pdf_content):
        """Test extraction validation feedback"""
        # Upload and extract
        files = {
            "file": ("invoice.pdf", sample_pdf_content, "application/pdf")
        }
        upload_response = client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=auth_headers
        )
        doc_id = upload_response.json()["data"]["document_id"]
        
        extraction_response = client.post(
            f"/api/v1/extraction/extract/{doc_id}",
            headers=auth_headers
        )
        extraction_id = extraction_response.json()["data"]["id"]
        
        # Validate
        validation_data = {
            "invoice_number": "CORRECTED-001",
            "total_amount": 15000.00
        }
        
        response = client.post(
            f"/api/v1/extraction/validate-extraction/{extraction_id}",
            json=validation_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True