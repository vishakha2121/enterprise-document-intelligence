"""
Tests for Fraud Detection API Routes
"""

import pytest
from unittest.mock import patch, AsyncMock
from fastapi import status


class TestFraudAPI:
    """Test cases for fraud detection endpoints"""
    
    @pytest.mark.asyncio
    async def test_check_document_fraud(self, client, auth_headers, sample_pdf_content):
        """Test fraud detection on document"""
        # Upload document
        files = {
            "file": ("document.pdf", sample_pdf_content, "application/pdf")
        }
        upload_response = client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=auth_headers
        )
        doc_id = upload_response.json()["data"]["document_id"]
        
        # Check fraud
        response = client.post(
            f"/api/v1/fraud/check/{doc_id}",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "risk_score" in data["data"]
        assert "risk_level" in data["data"]
    
    @pytest.mark.asyncio
    async def test_check_fraud_with_custom_threshold(self, client, auth_headers, sample_pdf_content):
        """Test fraud detection with custom threshold"""
        # Upload document
        files = {
            "file": ("document.pdf", sample_pdf_content, "application/pdf")
        }
        upload_response = client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=auth_headers
        )
        doc_id = upload_response.json()["data"]["document_id"]
        
        # Check fraud with threshold
        request_data = {
            "threshold": 0.5,
            "check_types": ["rule_based", "keyword"]
        }
        
        response = client.post(
            f"/api/v1/fraud/check/{doc_id}",
            json=request_data,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
    
    @pytest.mark.asyncio
    async def test_get_fraud_alerts(self, client, auth_headers):
        """Test get fraud alerts"""
        response = client.get(
            "/api/v1/fraud/alerts",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert isinstance(data["data"], list)
    
    @pytest.mark.asyncio
    async def test_get_fraud_alerts_with_filters(self, client, auth_headers):
        """Test get fraud alerts with filters"""
        response = client.get(
            "/api/v1/fraud/alerts?status=active&severity=high",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
    
    @pytest.mark.asyncio
    async def test_get_fraud_statistics(self, client, auth_headers):
        """Test get fraud statistics"""
        response = client.get(
            "/api/v1/fraud/stats?days=30",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "total_checks" in data["data"]
        assert "fraud_detected" in data["data"]
    
    @pytest.mark.asyncio
    async def test_get_fraud_rules(self, client, auth_headers):
        """Test get fraud detection rules"""
        response = client.get(
            "/api/v1/fraud/rules",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "rules" in data["data"]
    
    @pytest.mark.asyncio
    async def test_resolve_fraud_alert(self, client, auth_headers):
        """Test resolve fraud alert"""
        # First get an alert
        alerts_response = client.get(
            "/api/v1/fraud/alerts",
            headers=auth_headers
        )
        alerts = alerts_response.json()["data"]
        
        if alerts:
            alert_id = alerts[0]["id"]
            
            # Resolve alert
            resolution = {
                "notes": "False positive - legitimate document",
                "is_fraud": False
            }
            
            response = client.put(
                f"/api/v1/fraud/alert/{alert_id}/resolve",
                json=resolution,
                headers=auth_headers
            )
            
            assert response.status_code == status.HTTP_200_OK
            data = response.json()
            assert data["success"] is True
    
    @pytest.mark.asyncio
    async def test_generate_fraud_report(self, client, auth_headers, sample_pdf_content):
        """Test generate fraud report"""
        # Upload document
        files = {
            "file": ("document.pdf", sample_pdf_content, "application/pdf")
        }
        upload_response = client.post(
            "/api/v1/documents/upload",
            files=files,
            headers=auth_headers
        )
        doc_id = upload_response.json()["data"]["document_id"]
        
        # Generate report
        response = client.get(
            f"/api/v1/fraud/report/{doc_id}",
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "risk_assessment" in data["data"]


class TestBatchFraudAPI:
    """Test cases for batch fraud detection"""
    
    @pytest.mark.asyncio
    async def test_batch_fraud_check(self, client, auth_headers, sample_pdf_content):
        """Test batch fraud check for multiple documents"""
        # Upload multiple documents
        doc_ids = []
        for i in range(3):
            files = {
                "file": (f"doc_{i}.pdf", sample_pdf_content, "application/pdf")
            }
            response = client.post(
                "/api/v1/documents/upload",
                files=files,
                headers=auth_headers
            )
            doc_ids.append(response.json()["data"]["document_id"])
        
        # Batch fraud check
        response = client.post(
            "/api/v1/fraud/check-batch",
            json=doc_ids,
            headers=auth_headers
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["success"] is True
        assert "task_id" in data["data"]