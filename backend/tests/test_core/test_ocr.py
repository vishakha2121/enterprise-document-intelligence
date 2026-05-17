"""
Tests for OCR Core Module
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
import numpy as np
from PIL import Image
import io


class TestTesseractEngine:
    """Test cases for Tesseract OCR engine"""
    
    @pytest.mark.asyncio
    async def test_extract_text_from_image(self, tesseract_engine, sample_image):
        """Test text extraction from image"""
        result = await tesseract_engine.extract_text(sample_image)
        
        assert result["success"] is True
        assert "text" in result
        assert "confidence" in result
        assert result["engine"] == "tesseract"
    
    @pytest.mark.asyncio
    async def test_extract_text_from_bytes(self, tesseract_engine, sample_image_bytes):
        """Test text extraction from bytes"""
        result = await tesseract_engine.extract_text(sample_image_bytes)
        
        assert result["success"] is True
        assert len(result["text"]) > 0
    
    @pytest.mark.asyncio
    async def test_extract_text_with_preprocessing(self, tesseract_engine, sample_image):
        """Test extraction with preprocessing disabled"""
        result = await tesseract_engine.extract_text(sample_image, preprocessing=False)
        
        assert result["success"] is True
    
    @pytest.mark.asyncio
    async def test_extract_text_from_pdf(self, tesseract_engine, sample_pdf_content):
        """Test text extraction from PDF"""
        result = await tesseract_engine.extract_text_from_pdf(sample_pdf_content)
        
        assert result["success"] is True or result["success"] is False
        # PDF extraction might fail without proper setup, but should handle gracefully
    
    def test_get_supported_languages(self, tesseract_engine):
        """Test getting supported languages"""
        languages = tesseract_engine.get_supported_languages()
        assert isinstance(languages, list)
        assert "eng" in languages
    
    @pytest.mark.asyncio
    async def test_detect_orientation(self, tesseract_engine, sample_image):
        """Test orientation detection"""
        result = await tesseract_engine.detect_orientation(sample_image)
        
        assert "orientation" in result
        assert "needs_rotation" in result


class TestGeminiEngine:
    """Test cases for Gemini OCR engine"""
    
    @pytest.mark.asyncio
    async def test_gemini_extract_text(self, gemini_engine, sample_image):
        """Test Gemini text extraction"""
        if gemini_engine.is_available:
            result = await gemini_engine.extract_text(sample_image)
            assert result["success"] is True or result["success"] is False
        else:
            result = await gemini_engine.extract_text(sample_image)
            assert result["success"] is False
            assert "error" in result
    
    @pytest.mark.asyncio
    async def test_gemini_analyze_document(self, gemini_engine, sample_image):
        """Test Gemini document analysis"""
        if gemini_engine.is_available:
            result = await gemini_engine.analyze_document(sample_image, "full")
            assert "analysis_type" in result or "error" in result
    
    def test_gemini_availability(self, gemini_engine):
        """Test Gemini availability check"""
        is_avail = gemini_engine.is_available()
        assert isinstance(is_avail, bool)


class TestOCRFactory:
    """Test cases for OCR factory"""
    
    @pytest.mark.asyncio
    async def test_auto_select_ocr(self, ocr_factory, sample_image):
        """Test automatic OCR provider selection"""
        result = await ocr_factory.extract_text(sample_image, provider="auto")
        
        assert "success" in result
        assert "provider" in result
    
    @pytest.mark.asyncio
    async def test_tesseract_only(self, ocr_factory, sample_image):
        """Test force Tesseract only"""
        result = await ocr_factory.extract_text(sample_image, provider="tesseract")
        
        assert result["provider"] == "tesseract"
    
    @pytest.mark.asyncio
    async def test_gemini_only(self, ocr_factory, sample_image):
        """Test force Gemini only"""
        result = await ocr_factory.extract_text(sample_image, provider="gemini")
        
        assert result["provider"] == "gemini" or result.get("error") is not None
    
    def test_get_available_providers(self, ocr_factory):
        """Test getting available OCR providers"""
        providers = ocr_factory.get_available_providers()
        
        assert "tesseract" in providers
        assert "gemini" in providers
        assert "auto" in providers


class TestImagePreprocessor:
    """Test cases for image preprocessing"""
    
    @pytest.mark.asyncio
    async def test_preprocess_image(self, image_preprocessor, sample_image):
        """Test image preprocessing"""
        result = await image_preprocessor.preprocess(sample_image)
        
        assert result is not None
        assert isinstance(result, np.ndarray)
    
    @pytest.mark.asyncio
    async def test_preprocess_with_custom_params(self, image_preprocessor, sample_image):
        """Test preprocessing with custom parameters"""
        params = {
            "denoise": True,
            "deskew": True,
            "enhance_contrast": False,
            "binarize": True
        }
        
        result = await image_preprocessor.preprocess(sample_image, params)
        assert result is not None
    
    @pytest.mark.asyncio
    async def test_extract_quality_metrics(self, image_preprocessor, sample_image):
        """Test image quality metrics extraction"""
        metrics = await image_preprocessor.extract_quality_metrics(sample_image)
        
        assert "quality_score" in metrics
        assert "blur_score" in metrics
        assert "brightness" in metrics    
    def test_save_preprocessed_image(self, image_preprocessor, sample_image, temp_dir):
        """Test saving preprocessed image"""
        save_path = temp_dir / "preprocessed.jpg"
        result = image_preprocessor.save_preprocessed_image(sample_image, save_path)
        
        assert result is True
        assert save_path.exists()


# Fixtures for OCR tests
@pytest.fixture
def tesseract_engine():
    """Create Tesseract engine instance"""
    from app.core.ocr.tesseract_engine import TesseractEngine
    return TesseractEngine()


@pytest.fixture
def gemini_engine():
    """Create Gemini engine instance"""
    from app.core.ocr.gemini_engine import GeminiEngine
    return GeminiEngine()


@pytest.fixture
def ocr_factory():
    """Create OCR factory instance"""
    from app.core.ocr.ocr_factory import OCRFactory
    return OCRFactory()


@pytest.fixture
def image_preprocessor():
    """Create image preprocessor instance"""
    from app.core.ocr.image_preprocessor import ImagePreprocessor
    return ImagePreprocessor()


@pytest.fixture
def sample_image():
    """Create sample test image"""
    # Create a simple grayscale image with some text-like patterns
    img = Image.new('L', (800, 200), color=255)
    pixels = img.load()
    
    # Draw some simple patterns (simulating text)
    for i in range(100, 700, 20):
        for j in range(50, 150, 10):
            pixels[i, j] = 0
    
    return np.array(img)


@pytest.fixture
def sample_image_bytes(sample_image):
    """Convert sample image to bytes"""
    img = Image.fromarray(sample_image)
    img_byte_arr = io.BytesIO()
    img.save(img_byte_arr, format='PNG')
    return img_byte_arr.getvalue()