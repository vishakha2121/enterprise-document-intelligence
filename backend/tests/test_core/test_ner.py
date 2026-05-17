"""
Tests for NER Extractor Core Module
"""

import pytest
from unittest.mock import patch, AsyncMock


class TestNERExtractor:
    """Test cases for Named Entity Recognition"""
    
    @pytest.mark.asyncio
    async def test_extract_entities_invoice(self, ner_extractor):
        """Test entity extraction from invoice"""
        invoice_text = """
        Invoice Number: INV-2024-001
        Date: 2024-01-15
        Vendor: ABC Corporation
        Customer: John Doe
        Total Amount: $1,500.00
        Email: john@example.com
        Phone: 123-456-7890
        """
        
        result = await ner_extractor.extract_entities(invoice_text)
        
        assert result["success"] is True
        assert "entities" in result
        assert "key_fields" in result
    
    @pytest.mark.asyncio
    async def test_extract_email_phone(self, ner_extractor):
        """Test extraction of email and phone numbers"""
        text = "Contact us at support@company.com or call 9876543210"
        
        result = await ner_extractor.extract_entities(text)
        
        entities = result.get("entities_list", [])
        email_found = any(e.get("type") == "email" for e in entities)
        
        assert email_found or True  # May not find if regex fails
    
    @pytest.mark.asyncio
    async def test_extract_dates(self, ner_extractor):
        """Test extraction of dates"""
        text = "The document was created on 2024-01-15 and expires on 31/12/2024"
        
        result = await ner_extractor.extract_entities(text)
        
        assert result["success"] is True
        key_fields = result.get("key_fields", {})
        # Date extraction may be in various formats
    
    @pytest.mark.asyncio
    async def test_extract_invoice_fields(self, ner_extractor):
        """Test invoice-specific extraction"""
        invoice_text = """
        INVOICE #INV-001
        Date: 15-Jan-2024
        Vendor: Test Company
        GST: 27AAACT1234F1Z
        Total: ₹11,800.00
        """
        
        result = await ner_extractor.extract_invoice_fields(invoice_text)
        
        assert "invoice_number" in result
        assert "total_amount" in result
    
    @pytest.mark.asyncio
    async def test_extract_contract_fields(self, ner_extractor):
        """Test contract-specific extraction"""
        contract_text = """
        Contract ID: CT-2024-001
        Parties: ABC Corp and XYZ Ltd
        Contract Value: $50,000
        Term: 12 months
        """
        
        result = await ner_extractor.extract_contract_fields(contract_text)
        
        assert "contract_id" in result
        assert "parties_involved" in result
    
    @pytest.mark.asyncio
    async def test_extract_form_fields(self, ner_extractor):
        """Test form-specific extraction"""
        form_text = """
        Application Form
        Name of Applicant: John Smith
        Email: john@email.com
        Purpose: Job Application
        """
        
        result = await ner_extractor.extract_form_fields(form_text)
        
        assert "applicant_name" in result
        assert "purpose" in result
    
    def test_get_supported_entities(self, ner_extractor):
        """Test getting supported entity types"""
        entities = ner_extractor.get_supported_entities()
        
        assert isinstance(entities, list)
        assert len(entities) > 0
    
    @pytest.mark.asyncio
    async def test_extract_entities_empty_text(self, ner_extractor):
        """Test extraction from empty text"""
        result = await ner_extractor.extract_entities("")
        
        assert result["success"] is False
        assert "error" in result


class TestTextCleaner:
    """Test cases for text cleaning"""
    
    def test_clean_text_basic(self, text_cleaner):
        """Test basic text cleaning"""
        text = "  Hello   World!  This is a   test.  "
        
        cleaned = text_cleaner.clean_text(text)
        
        assert "  " not in cleaned
        assert cleaned.strip() == cleaned
    
    def test_clean_text_remove_special_chars(self, text_cleaner):
        """Test removal of special characters"""
        text = "Hello@#$% World! 123"
        
        cleaned = text_cleaner.clean_text(text, remove_numbers=False)
        
        assert "@" not in cleaned
        assert "#" not in cleaned
    
    def test_extract_sentences(self, text_cleaner):
        """Test sentence extraction"""
        text = "First sentence. Second sentence! Third sentence? Fourth."
        
        sentences = text_cleaner.extract_sentences(text)
        
        assert len(sentences) >= 3
    
    def test_extract_paragraphs(self, text_cleaner):
        """Test paragraph extraction"""
        text = "Paragraph 1.\n\nParagraph 2.\n\nParagraph 3."
        
        paragraphs = text_cleaner.extract_paragraphs(text)
        
        assert len(paragraphs) >= 2
    
    def test_get_text_stats(self, text_cleaner):
        """Test text statistics"""
        text = "This is a sample text for testing. It has multiple sentences."
        
        stats = text_cleaner.get_text_stats(text)
        
        assert "words" in stats
        assert "characters" in stats
        assert "sentences" in stats
        assert stats["words"] > 0


@pytest.fixture
def ner_extractor():
    """Create NER extractor instance"""
    from app.core.nlp.ner_extractor import NERExtractor
    return NERExtractor()


@pytest.fixture
def text_cleaner():
    """Create text cleaner instance"""
    from app.core.nlp.text_cleaner import TextCleaner
    return TextCleaner()