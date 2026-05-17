"""
Tests for Fraud Detection Service
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from datetime import datetime, timedelta


class TestFraudService:
    """Test cases for fraud detection service"""
    
    @pytest.mark.asyncio
    async def test_check_document_fraud(self, fraud_service, db_session, sample_document):
        """Test fraud detection on document"""
        db_session.add(sample_document)
        await db_session.commit()
        
        result = await fraud_service.check_document_fraud(
            document_id=sample_document.id,
            user_id=1
        )
        
        assert result is not None
        assert "risk_score" in result
        assert "risk_level" in result
        assert "is_fraudulent" in result
    
    @pytest.mark.asyncio
    async def test_check_fraud_with_custom_threshold(self, fraud_service, db_session, sample_document):
        """Test fraud detection with custom threshold"""
        db_session.add(sample_document)
        await db_session.commit()
        
        result = await fraud_service.check_document_fraud(
            document_id=sample_document.id,
            user_id=1,
            threshold=0.5
        )
        
        assert result is not None
        assert 0 <= result["risk_score"] <= 1
    
    @pytest.mark.asyncio
    async def test_get_fraud_alerts(self, fraud_service, db_session, fraud_logs):
        """Test get fraud alerts"""
        for log in fraud_logs:
            db_session.add(log)
        await db_session.commit()
        
        alerts = await fraud_service.get_fraud_alerts(user_id=1)
        
        assert isinstance(alerts, list)
    
    @pytest.mark.asyncio
    async def test_get_fraud_alerts_with_filters(self, fraud_service, db_session, fraud_logs):
        """Test get fraud alerts with filters"""
        for log in fraud_logs:
            db_session.add(log)
        await db_session.commit()
        
        alerts = await fraud_service.get_fraud_alerts(
            user_id=1,
            severity="high",
            limit=10
        )
        
        for alert in alerts:
            assert alert.risk_level in ["high", "critical"]
    
    @pytest.mark.asyncio
    async def test_resolve_alert(self, fraud_service, db_session, fraud_log):
        """Test resolve fraud alert"""
        db_session.add(fraud_log)
        await db_session.commit()
        
        result = await fraud_service.resolve_alert(
            alert_id=fraud_log.id,
            user_id=1,
            resolution_notes="False positive",
            is_fraud=False
        )
        
        assert result is True
        
        # Verify alert status
        resolved_alert = await fraud_service.get_fraud_alert(fraud_log.id, 1)
        assert resolved_alert.alert_status == "false_positive"
    
    @pytest.mark.asyncio
    async def test_get_fraud_statistics(self, fraud_service, db_session, fraud_logs):
        """Test get fraud statistics"""
        for log in fraud_logs:
            db_session.add(log)
        await db_session.commit()
        
        stats = await fraud_service.get_fraud_statistics(user_id=1, days=30)
        
        assert "total_checks" in stats
        assert "fraud_detected" in stats
        assert "fraud_rate" in stats
    
    @pytest.mark.asyncio
    async def test_create_fraud_alert(self, fraud_service, db_session, sample_document):
        """Test create fraud alert"""
        db_session.add(sample_document)
        await db_session.commit()
        
        fraud_result = {
            "risk_score": 0.85,
            "risk_level": "high",
            "fraud_type": "amount_mismatch",
            "evidence": [{"type": "test", "description": "Test evidence"}]
        }
        
        alert = await fraud_service.create_fraud_alert(
            document_id=sample_document.id,
            user_id=1,
            fraud_result=fraud_result
        )
        
        assert alert is not None
        assert alert.risk_score == 0.85
        assert alert.risk_level == "high"
    
    @pytest.mark.asyncio
    async def test_generate_fraud_report(self, fraud_service, db_session, sample_document):
        """Test generate fraud report"""
        db_session.add(sample_document)
        await db_session.commit()
        
        report = await fraud_service.generate_fraud_report(
            document_id=sample_document.id,
            user_id=1
        )
        
        if report:
            assert "risk_assessment" in report
            assert "recommendations" in report
    
    @pytest.mark.asyncio
    async def test_get_detection_rules(self, fraud_service):
        """Test get detection rules"""
        rules = await fraud_service.get_detection_rules()
        
        assert isinstance(rules, list)
    
    @pytest.mark.asyncio
    async def test_validate_signature(self, fraud_service):
        """Test signature validation"""
        result = await fraud_service.validate_signature(
            document_id=1,
            user_id=1,
            signature_data={"signer": "Test Signer"}
        )
        
        assert "valid" in result
        assert "confidence" in result


class TestFraudDetectorIntegration:
    """Integration tests for fraud detector"""
    
    @pytest.mark.asyncio
    async def test_fraud_detection_pipeline(self, fraud_service, sample_fraudulent_text):
        """Test complete fraud detection pipeline"""
        # This would require more setup
        result = await fraud_service.check_document_fraud(document_id=1, user_id=1)
        
        assert result is not None
        assert "risk_score" in result
    
    @pytest.mark.asyncio
    async def test_amount_anomaly_detection(self, amount_anomaly_detector):
        """Test amount anomaly detection"""
        extracted_data = {
            "subtotal": 1000,
            "tax_amount": 180,
            "total_amount": 1180,
            "line_items": [
                {"amount": 500},
                {"amount": 500}
            ]
        }
        
        anomalies = await amount_anomaly_detector.detect_anomalies(extracted_data)
        
        assert isinstance(anomalies, list)


# Fixtures
@pytest.fixture
def fraud_service(db_session, mock_cache_service):
    """Create fraud service instance"""
    from app.services.fraud_service import FraudService
    return FraudService(db_session, mock_cache_service)


@pytest.fixture
def amount_anomaly_detector():
    """Create amount anomaly detector instance"""
    from app.core.fraud.amount_anomaly import AmountAnomalyDetector
    return AmountAnomalyDetector()


@pytest.fixture
def fraud_log():
    """Create sample fraud log"""
    from app.database.models.fraud_log import FraudLog
    
    return FraudLog(
        document_id=1,
        risk_score=0.85,
        risk_level="high",
        fraud_type="amount_mismatch",
        detection_methods=["rule_based", "anomaly"],
        evidence=[{"type": "amount_mismatch", "description": "Total doesn't match"}],
        alert_status="active",
        created_at=datetime.now()
    )


@pytest.fixture
def fraud_logs():
    """Create multiple fraud logs"""
    from app.database.models.fraud_log import FraudLog
    
    logs = []
    risk_levels = ["low", "medium", "high", "critical"]
    
    for i, level in enumerate(risk_levels):
        log = FraudLog(
            document_id=i + 1,
            risk_score=0.2 + (i * 0.25),
            risk_level=level,
            fraud_type="test_fraud" if level in ["high", "critical"] else None,
            detection_methods=["test"],
            evidence=[],
            alert_status="active",
            created_at=datetime.now() - timedelta(days=i)
        )
        logs.append(log)
    
    return logs


@pytest.fixture
def sample_fraudulent_text():
    """Sample text with fraud indicators"""
    return """
    URGENT: Please process this invoice immediately.
    This is a CONFIDENTIAL document. DO NOT SHARE.
    Original amount: $1,000
    Revised amount: $10,000
    """