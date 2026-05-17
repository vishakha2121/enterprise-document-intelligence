"""
Tests for BERT Classifier Core Module
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock


class TestBERTClassifier:
    """Test cases for BERT document classifier"""
    
    @pytest.mark.asyncio
    async def test_classify_invoice(self, bert_classifier):
        """Test classification of invoice document"""
        invoice_text = """
        INVOICE
        Invoice Number: INV-2024-001
        Date: 2024-01-15
        Vendor: ABC Corp
        Total Amount: $1,500.00
        Payment Due: 2024-02-15
        """
        
        result = await bert_classifier.classify(invoice_text)
        
        assert result["success"] is True
        assert "document_type" in result
        assert "confidence" in result
    
    @pytest.mark.asyncio
    async def test_classify_contract(self, bert_classifier):
        """Test classification of contract document"""
        contract_text = """
        SERVICE AGREEMENT
        This Agreement is made between Company A and Company B.
        Term: 12 months
        Payment: $10,000 per month
        Governing Law: State of Delaware
        """
        
        result = await bert_classifier.classify(contract_text)
        
        assert result["success"] is True
        assert result["document_type"] in ["contract", "other"]
    
    @pytest.mark.asyncio
    async def test_classify_with_top_k(self, bert_classifier):
        """Test classification with top K predictions"""
        text = "This is a sample document"
        
        result = await bert_classifier.classify(text, return_top_k=3)
        
        assert result["success"] is True
        assert len(result["top_predictions"]) <= 3
    
    @pytest.mark.asyncio
    async def test_classify_empty_text(self, bert_classifier):
        """Test classification with empty text"""
        result = await bert_classifier.classify("")
        
        assert result["success"] is False
        assert "error" in result
    
    @pytest.mark.asyncio
    async def test_batch_classify(self, bert_classifier):
        """Test batch classification"""
        texts = [
            "Invoice document with amounts",
            "Contract agreement between parties",
            "Application form for registration"
        ]
        
        results = await bert_classifier.batch_classify(texts)
        
        assert len(results) == 3
        for result in results:
            assert "document_type" in result
    
    async def test_get_model_info(self, bert_classifier):
        """Test getting model information"""
        info = await bert_classifier.get_model_info()
        
        assert "model_name" in info
        assert "num_classes" in info
        assert "document_types" in info
    
    def test_get_confidence_score(self, bert_classifier):
        """Test synchronous confidence score"""
        score = bert_classifier.get_confidence_score("Sample invoice text")
        
        assert isinstance(score, float)
        assert 0 <= score <= 1


class TestRuleBasedFallback:
    """Test cases for rule-based fallback classifier"""
    
    @pytest.mark.asyncio
    async def test_rule_based_invoice(self, bert_classifier_without_model):
        """Test rule-based invoice detection"""
        text = "INVOICE #12345\nAmount Due: $500"
        
        result = await bert_classifier_without_model.classify(text)
        
        assert result["model_used"] == "rule_based_fallback"
        assert result["document_type"] == "invoice"
    
    @pytest.mark.asyncio
    async def test_rule_based_contract(self, bert_classifier_without_model):
        """Test rule-based contract detection"""
        text = "CONTRACT AGREEMENT between parties"
        
        result = await bert_classifier_without_model.classify(text)
        
        assert result["document_type"] == "contract"


@pytest.fixture
def bert_classifier():
    """Create BERT classifier instance"""
    from app.core.nlp.bert_classifier import BERTClassifier
    return BERTClassifier()


@pytest.fixture
def bert_classifier_without_model():
    """Create BERT classifier with model loading disabled"""
    from app.core.nlp.bert_classifier import BERTClassifier
    
    classifier = BERTClassifier()
    classifier.is_loaded = False
    return classifier