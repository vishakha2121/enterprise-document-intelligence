"""
Tesseract OCR Engine
High-performance OCR using Tesseract with preprocessing
"""

import cv2
import numpy as np
import pytesseract
from PIL import Image
import io
import logging
from typing import Union, Dict, Any, Optional, List, Tuple
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time

from app.config import settings

logger = logging.getLogger(__name__)

class TesseractEngine:
    """
    Tesseract OCR Engine for text extraction from images and PDFs
    Supports multiple languages, preprocessing, and confidence scoring
    """
    
    def __init__(self):
        """Initialize Tesseract OCR engine"""
        self.tesseract_path = settings.TESSERACT_PATH
        self.language = settings.OCR_LANGUAGE
        self.config = settings.OCR_CONFIG
        
        # Set Tesseract path if provided
        if self.tesseract_path != "tesseract":
            pytesseract.pytesseract.tesseract_cmd = self.tesseract_path
        
        # Thread pool for async operations
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        logger.info(f"Tesseract OCR Engine initialized with language: {self.language}")
    
    async def extract_text(
        self,
        image_data: Union[bytes, np.ndarray, Path, str],
        preprocessing: bool = True,
        psm: Optional[int] = None,
        oem: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Extract text from image
        
        Args:
            image_data: Image data (bytes, numpy array, or file path)
            preprocessing: Apply image preprocessing
            psm: Page segmentation mode
            oem: OCR Engine mode
        
        Returns:
            Dictionary with extracted text and metadata
        """
        start_time = time.time()
        
        try:
            # Load image
            image = self._load_image(image_data)
            
            # Apply preprocessing
            if preprocessing:
                image = self._preprocess_image(image)
            
            # Configure Tesseract
            config_string = self._build_config_string(psm, oem)
            
            # Run OCR in thread pool
            loop = asyncio.get_event_loop()
            ocr_result = await loop.run_in_executor(
                self.executor,
                lambda: pytesseract.image_to_data(
                    image,
                    lang=self.language,
                    config=config_string,
                    output_type=pytesseract.Output.DICT
                )
            )
            
            # Extract text and confidence
            text, confidence, words_with_conf = self._process_ocr_result(ocr_result)
            
            processing_time = (time.time() - start_time) * 1000
            
            return {
                "success": True,
                "text": text,
                "confidence": confidence,
                "words": words_with_conf,
                "processing_time_ms": processing_time,
                "engine": "tesseract",
                "language": self.language
            }
        
        except Exception as e:
            logger.error(f"Tesseract OCR failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "text": "",
                "confidence": 0.0,
                "processing_time_ms": (time.time() - start_time) * 1000,
                "engine": "tesseract"
            }
    
    async def extract_text_from_pdf(
        self,
        pdf_data: bytes,
        page_numbers: Optional[List[int]] = None
    ) -> Dict[str, Any]:
        """
        Extract text from PDF (converts PDF pages to images)
        
        Args:
            pdf_data: PDF file bytes
            page_numbers: Specific pages to extract (None for all)
        
        Returns:
            Dictionary with extracted text per page
        """
        try:
            from pdf2image import convert_from_bytes
            
            start_time = time.time()
            
            # Convert PDF to images
            images = convert_from_bytes(
                pdf_data,
                dpi=300,
                fmt='jpeg'
            )
            
            # Select specific pages
            if page_numbers:
                images = [images[i-1] for i in page_numbers if i <= len(images)]
            
            # Extract text from each page
            pages_result = []
            full_text = ""
            total_confidence = 0
            
            for idx, image in enumerate(images):
                # Convert PIL Image to numpy array
                img_np = np.array(image)
                
                # Extract text
                result = await self.extract_text(img_np, preprocessing=True)
                
                pages_result.append({
                    "page_number": idx + 1,
                    "text": result["text"],
                    "confidence": result["confidence"]
                })
                
                full_text += f"\n--- Page {idx + 1} ---\n{result['text']}\n"
                total_confidence += result["confidence"]
            
            avg_confidence = total_confidence / len(images) if images else 0
            
            return {
                "success": True,
                "full_text": full_text,
                "pages": pages_result,
                "total_pages": len(images),
                "average_confidence": avg_confidence,
                "processing_time_ms": (time.time() - start_time) * 1000,
                "engine": "tesseract"
            }
        
        except Exception as e:
            logger.error(f"PDF text extraction failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "full_text": "",
                "pages": []
            }
    
    def _load_image(self, image_data: Union[bytes, np.ndarray, Path, str]) -> np.ndarray:
        """Load image from various input types"""
        if isinstance(image_data, bytes):
            # Convert bytes to numpy array
            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        elif isinstance(image_data, (Path, str)):
            # Load from file path
            image = cv2.imread(str(image_data))
        elif isinstance(image_data, np.ndarray):
            image = image_data
        else:
            raise ValueError(f"Unsupported image data type: {type(image_data)}")
        
        if image is None:
            raise ValueError("Failed to load image")
        
        return image
    
    def _preprocess_image(self, image: np.ndarray) -> np.ndarray:
        """
        Apply preprocessing to improve OCR accuracy
        """
        # Convert to grayscale
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Apply thresholding (binarization)
        _, thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Denoise
        denoised = cv2.medianBlur(thresh, 1)
        
        # Deskew (correct rotation)
        coords = np.column_stack(np.where(denoised > 0))
        if len(coords) > 0:
            angle = cv2.minAreaRect(coords)[-1]
            if angle < -45:
                angle = -(90 + angle)
            else:
                angle = -angle
            
            if abs(angle) > 0.5:
                (h, w) = denoised.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                denoised = cv2.warpAffine(denoised, M, (w, h), 
                                          flags=cv2.INTER_CUBIC, 
                                          borderMode=cv2.BORDER_REPLICATE)
        
        # Enhance contrast
        enhanced = cv2.convertScaleAbs(denoised, alpha=1.5, beta=0)
        
        return enhanced
    
    def _build_config_string(self, psm: Optional[int] = None, oem: Optional[int] = None) -> str:
        """Build Tesseract configuration string"""
        config_parts = []
        
        # Page segmentation mode
        psm_val = psm if psm is not None else self.config.get("psm", 3)
        config_parts.append(f"--psm {psm_val}")
        
        # OCR Engine mode
        oem_val = oem if oem is not None else self.config.get("oem", 3)
        config_parts.append(f"--oem {oem_val}")
        
        # Additional config
        config_parts.append("-c tessedit_char_whitelist=ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,-:;$%&@#!?/\\()[]{}<>|~`^+=*")
        config_parts.append("--dpi 300")
        
        return " ".join(config_parts)
    
    def _process_ocr_result(self, ocr_result: Dict) -> Tuple[str, float, List[Dict]]:
        """
        Process Tesseract OCR result and calculate confidence
        """
        text_lines = []
        words_with_conf = []
        total_conf = 0
        word_count = 0
        
        for i, text in enumerate(ocr_result['text']):
            if text.strip():
                conf = int(ocr_result['conf'][i]) / 100.0
                if conf > 0:
                    word_info = {
                        "text": text,
                        "confidence": conf,
                        "bbox": {
                            "x": ocr_result['left'][i],
                            "y": ocr_result['top'][i],
                            "width": ocr_result['width'][i],
                            "height": ocr_result['height'][i]
                        },
                        "line_num": ocr_result['line_num'][i]
                    }
                    words_with_conf.append(word_info)
                    total_conf += conf
                    word_count += 1
                    text_lines.append(text)
        
        full_text = " ".join(text_lines)
        avg_confidence = total_conf / word_count if word_count > 0 else 0.0
        
        return full_text, avg_confidence, words_with_conf
    
    def extract_text_sync(self, image_path: str) -> str:
        """
        Synchronous text extraction (for testing)
        
        Args:
            image_path: Path to image file
        
        Returns:
            Extracted text
        """
        try:
            image = cv2.imread(image_path)
            if image is None:
                return ""
            
            processed = self._preprocess_image(image)
            text = pytesseract.image_to_string(processed, lang=self.language)
            return text.strip()
        
        except Exception as e:
            logger.error(f"Sync text extraction failed: {str(e)}")
            return ""
    
    def get_supported_languages(self) -> List[str]:
        """
        Get list of supported Tesseract languages
        """
        try:
            languages = pytesseract.get_languages(config='')
            return languages
        except Exception as e:
            logger.error(f"Failed to get languages: {str(e)}")
            return ['eng']
    
    async def detect_orientation(self, image_data: Union[bytes, np.ndarray]) -> Dict[str, Any]:
        """
        Detect image orientation for automatic deskewing
        """
        try:
            image = self._load_image(image_data)
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(image.shape) == 3 else image
            
            # Detect using Tesseract
            loop = asyncio.get_event_loop()
            osd_result = await loop.run_in_executor(
                self.executor,
                lambda: pytesseract.image_to_osd(gray)
            )
            
            # Parse OSD result
            orientation = 0
            for line in osd_result.split('\n'):
                if 'Rotate:' in line:
                    orientation = int(line.split(':')[-1].strip())
                    break
            
            return {
                "orientation": orientation,
                "needs_rotation": orientation != 0,
                "confidence": 0.9
            }
        
        except Exception as e:
            logger.error(f"Orientation detection failed: {str(e)}")
            return {"orientation": 0, "needs_rotation": False, "confidence": 0.0}