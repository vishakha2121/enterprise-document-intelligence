"""
OCR Module Package
Handles Optical Character Recognition using Tesseract and Gemini AI
"""

from app.core.ocr.tesseract_engine import TesseractEngine
from app.core.ocr.gemini_engine import GeminiEngine
from app.core.ocr.ocr_factory import OCRFactory
from app.core.ocr.image_preprocessor import ImagePreprocessor

__all__ = [
    "TesseractEngine",
    "GeminiEngine",
    "OCRFactory",
    "ImagePreprocessor"
]