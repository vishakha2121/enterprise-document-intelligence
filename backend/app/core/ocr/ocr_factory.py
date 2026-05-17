"""
OCR Factory Pattern
Smart routing between Tesseract and Gemini based on document complexity
"""

import logging
from typing import Dict, Any, Union, Optional
from enum import Enum
from pathlib import Path
import time

from app.core.ocr.tesseract_engine import TesseractEngine
from app.core.ocr.gemini_engine import GeminiEngine
from app.core.ocr.image_preprocessor import ImagePreprocessor
from app.config import settings

logger = logging.getLogger(__name__)

class OCRProvider(str, Enum):
    """OCR provider options"""
    TESSERACT = "tesseract"
    GEMINI = "gemini"
    AUTO = "auto"
    HYBRID = "hybrid"

class OCRFactory:
    """
    Factory for OCR engines with automatic provider selection
    Routes documents to appropriate OCR engine based on complexity
    """
    
    def __init__(self):
        """Initialize OCR engines"""
        self.tesseract = TesseractEngine()
        self.gemini = GeminiEngine()
        self.preprocessor = ImagePreprocessor()
        
        # Complexity thresholds
        self.complexity_threshold = 0.6  # Use Gemini above this threshold
        self.min_confidence_tesseract = 0.7  # Fallback to Gemini if confidence below this
        
        logger.info("OCR Factory initialized with Tesseract and Gemini")
    
    async def extract_text(
        self,
        image_data: Union[bytes, str, Path],
        provider: OCRProvider = OCRProvider.AUTO,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Extract text using appropriate OCR provider
        
        Args:
            image_data: Document image
            provider: OCR provider to use (auto, tesseract, gemini, hybrid)
            **kwargs: Additional arguments for specific engines
        
        Returns:
            Extraction results with metadata
        """
        start_time = time.time()
        
        if provider == OCRProvider.TESSERACT:
            return await self._use_tesseract(image_data, **kwargs)
        
        elif provider == OCRProvider.GEMINI:
            if not self.gemini.is_available:
                logger.warning("Gemini not available, falling back to Tesseract")
                return await self._use_tesseract(image_data, **kwargs)
            return await self._use_gemini(image_data, **kwargs)
        
        elif provider == OCRProvider.HYBRID:
            return await self._use_hybrid(image_data, **kwargs)
        
        else:  # AUTO
            return await self._auto_select(image_data, **kwargs)
    
    async def _auto_select(
        self,
        image_data: Union[bytes, str, Path],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Automatically select best OCR provider based on document analysis
        """
        try:
            # Analyze document complexity
            complexity_score = await self._analyze_complexity(image_data)
            
            logger.info(f"Document complexity score: {complexity_score}")
            
            # Route based on complexity
            if complexity_score > self.complexity_threshold and self.gemini.is_available:
                logger.info("Using Gemini for complex document")
                result = await self._use_gemini(image_data, **kwargs)
            else:
                logger.info("Using Tesseract for simple document")
                result = await self._use_tesseract(image_data, **kwargs)
                
                # Fallback to Gemini if Tesseract confidence is low
                if (self.gemini.is_available and 
                    result.get("success") and 
                    result.get("confidence", 0) < self.min_confidence_tesseract):
                    logger.info("Tesseract confidence low, falling back to Gemini")
                    gemini_result = await self._use_gemini(image_data, **kwargs)
                    if gemini_result.get("success"):
                        result = gemini_result
                        result["fallback_used"] = True
            
            result["provider_selection"] = "auto"
            return result
        
        except Exception as e:
            logger.error(f"Auto-selection failed: {str(e)}")
            # Default to Tesseract
            return await self._use_tesseract(image_data, **kwargs)
    
    async def _use_tesseract(
        self,
        image_data: Union[bytes, str, Path],
        **kwargs
    ) -> Dict[str, Any]:
        """Use Tesseract OCR engine"""
        try:
            # Preprocess for better results
            preprocessed = await self.preprocessor.preprocess(image_data)
            
            # Extract text
            result = await self.tesseract.extract_text(
                preprocessed,
                preprocessing=kwargs.get('preprocessing', True),
                psm=kwargs.get('psm'),
                oem=kwargs.get('oem')
            )
            
            result["provider"] = "tesseract"
            return result
        
        except Exception as e:
            logger.error(f"Tesseract extraction failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "provider": "tesseract",
                "text": ""
            }
    
    async def _use_gemini(
        self,
        image_data: Union[bytes, str, Path],
        **kwargs
    ) -> Dict[str, Any]:
        """Use Gemini OCR engine"""
        if not self.gemini.is_available:
            return {
                "success": False,
                "error": "Gemini API not available",
                "provider": "gemini",
                "text": ""
            }
        
        try:
            result = await self.gemini.extract_text(
                image_data,
                prompt=kwargs.get('prompt'),
                extract_structured=kwargs.get('extract_structured', True)
            )
            
            result["provider"] = "gemini"
            return result
        
        except Exception as e:
            logger.error(f"Gemini extraction failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "provider": "gemini",
                "text": ""
            }
    
    async def _use_hybrid(
        self,
        image_data: Union[bytes, str, Path],
        **kwargs
    ) -> Dict[str, Any]:
        """
        Hybrid approach: Use both Tesseract and Gemini,
        then combine results for best accuracy
        """
        # Run both OCR engines in parallel
        tesseract_task = self._use_tesseract(image_data, **kwargs)
        gemini_task = self._use_gemini(image_data, **kwargs) if self.gemini.is_available else None
        
        tesseract_result = await tesseract_task
        gemini_result = await gemini_task if gemini_task else None
        
        # Combine results
        combined_result = self._combine_results(tesseract_result, gemini_result)
        combined_result["provider"] = "hybrid"
        
        return combined_result
    
    async def _analyze_complexity(self, image_data: Union[bytes, str, Path]) -> float:
        """
        Analyze document complexity to determine best OCR engine
        Returns score between 0 (simple) and 1 (complex)
        """
        try:
            # Load image
            image = self.preprocessor._load_image(image_data)
            
            complexity_score = 0.0
            
            # Factor 1: Image resolution and size
            height, width = image.shape[:2] if hasattr(image, 'shape') else (0, 0)
            if width * height > 2000000:  # > 2 megapixels
                complexity_score += 0.2
            
            # Factor 2: Color vs grayscale (color is more complex)
            if len(image.shape) == 3 and image.shape[2] == 3:
                complexity_score += 0.15
            
            # Factor 3: Quick Tesseract confidence test on small sample
            try:
                import cv2
                small = cv2.resize(image, (800, 600))
                test_result = await self.tesseract.extract_text(small, preprocessing=True)
                if test_result.get("confidence", 0) < 0.5:
                    complexity_score += 0.3
            except:
                pass
            
            # Factor 4: Language detection (multiple languages = complex)
            # This would require additional analysis
            
            # Cap at 1.0
            return min(complexity_score, 1.0)
        
        except Exception as e:
            logger.error(f"Complexity analysis failed: {str(e)}")
            return 0.5  # Default medium complexity
    
    def _combine_results(
        self,
        tesseract_result: Dict[str, Any],
        gemini_result: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Combine results from multiple OCR engines"""
        if not gemini_result or not gemini_result.get("success"):
            return tesseract_result
        
        if not tesseract_result.get("success"):
            return gemini_result
        
        # Choose best text based on confidence
        tesseract_conf = tesseract_result.get("confidence", 0)
        gemini_conf = gemini_result.get("confidence", 0.8)  # Gemini doesn't provide confidence
        
        if gemini_conf > tesseract_conf + 0.1:
            # Gemini is significantly better
            combined_text = gemini_result.get("text", "")
            primary_engine = "gemini"
        else:
            # Tesseract is good enough, or use both
            combined_text = tesseract_result.get("text", "")
            primary_engine = "tesseract"
            
            # Append Gemini's structured data if available
            if gemini_result.get("structured_data"):
                combined_text += "\n\n--- Extracted Structured Data ---\n"
                combined_text += str(gemini_result.get("structured_data", {}))
        
        return {
            "success": True,
            "text": combined_text,
            "confidence": max(tesseract_conf, gemini_conf),
            "primary_engine": primary_engine,
            "tesseract_used": True,
            "gemini_used": True,
            "tesseract_confidence": tesseract_conf,
            "gemini_confidence": gemini_conf,
            "processing_time_ms": tesseract_result.get("processing_time_ms", 0) + 
                                 gemini_result.get("processing_time_ms", 0)
        }
    
    def get_available_providers(self) -> Dict[str, bool]:
        """Get list of available OCR providers"""
        return {
            "tesseract": True,  # Tesseract is always available if installed
            "gemini": self.gemini.is_available,
            "auto": True,
            "hybrid": self.gemini.is_available
        }