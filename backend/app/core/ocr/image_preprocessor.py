"""
Image Preprocessor for OCR Enhancement
Improves image quality before OCR processing
"""

import cv2
import numpy as np
from PIL import Image
import io
import logging
from typing import Union, Tuple, Optional, Dict, Any
from pathlib import Path
import asyncio

logger = logging.getLogger(__name__)

class ImagePreprocessor:
    """
    Advanced image preprocessing for better OCR accuracy
    Includes deskewing, denoising, contrast enhancement, and more
    """
    
    def __init__(self):
        """Initialize preprocessor with default parameters"""
        self.default_params = {
            "denoise": True,
            "deskew": True,
            "enhance_contrast": True,
            "binarize": True,
            "remove_borders": True,
            "dpi_target": 300
        }
    
    async def preprocess(
        self,
        image_data: Union[bytes, str, Path, np.ndarray],
        params: Optional[Dict[str, Any]] = None
    ) -> np.ndarray:
        """
        Preprocess image for OCR
        
        Args:
            image_data: Input image
            params: Preprocessing parameters
        
        Returns:
            Preprocessed image as numpy array
        """
        try:
            # Load image
            image = self._load_image(image_data)
            
            # Merge with default params
            if params is None:
                params = self.default_params
            else:
                params = {**self.default_params, **params}
            
            # Apply preprocessing steps
            if params.get("denoise", True):
                image = self._denoise(image)
            
            if params.get("enhance_contrast", True):
                image = self._enhance_contrast(image)
            
            if params.get("deskew", True):
                image = self._deskew(image)
            
            if params.get("binarize", True):
                image = self._binarize(image)
            
            if params.get("remove_borders", True):
                image = self._remove_borders(image)
            
            # Resize to target DPI if needed
            if params.get("dpi_target"):
                image = self._resize_to_dpi(image, params["dpi_target"])
            
            return image
        
        except Exception as e:
            logger.error(f"Image preprocessing failed: {str(e)}")
            # Return original image if preprocessing fails
            return self._load_image(image_data)
    
    def _load_image(self, image_data: Union[bytes, str, Path, np.ndarray]) -> np.ndarray:
        """Load image from various input types"""
        if isinstance(image_data, bytes):
            nparr = np.frombuffer(image_data, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        elif isinstance(image_data, (str, Path)):
            image = cv2.imread(str(image_data))
        elif isinstance(image_data, np.ndarray):
            image = image_data
        elif isinstance(image_data, Image.Image):
            image = np.array(image_data)
            if len(image.shape) == 3 and image.shape[2] == 3:
                image = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        else:
            raise ValueError(f"Unsupported image type: {type(image_data)}")
        
        if image is None:
            raise ValueError("Failed to load image")
        
        return image
    
    def _denoise(self, image: np.ndarray) -> np.ndarray:
        """Apply noise reduction"""
        if len(image.shape) == 3:
            # Color image
            return cv2.fastNlMeansDenoisingColored(image, None, 10, 10, 7, 21)
        else:
            # Grayscale
            return cv2.fastNlMeansDenoising(image, None, 10, 7, 21)
    
    def _enhance_contrast(self, image: np.ndarray) -> np.ndarray:
        """Enhance image contrast using CLAHE"""
        if len(image.shape) == 3:
            # Convert to LAB color space
            lab = cv2.cvtColor(image, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            
            # Apply CLAHE to L channel
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            
            # Merge back
            lab = cv2.merge([l, a, b])
            return cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        else:
            # Grayscale
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            return clahe.apply(image)
    
    def _deskew(self, image: np.ndarray) -> np.ndarray:
        """Correct image skew/rotation"""
        try:
            # Convert to grayscale if needed
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            # Threshold
            thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
            
            # Find all contours
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                return image
            
            # Get minimum area rectangle for largest contour
            largest_contour = max(contours, key=cv2.contourArea)
            rect = cv2.minAreaRect(largest_contour)
            angle = rect[2]
            
            # Adjust angle
            if angle < -45:
                angle = 90 + angle
            
            # Apply rotation only if skew is significant
            if abs(angle) > 0.5:
                (h, w) = image.shape[:2]
                center = (w // 2, h // 2)
                M = cv2.getRotationMatrix2D(center, angle, 1.0)
                rotated = cv2.warpAffine(image, M, (w, h),
                                         flags=cv2.INTER_CUBIC,
                                         borderMode=cv2.BORDER_REPLICATE)
                return rotated
            
            return image
        
        except Exception as e:
            logger.warning(f"Deskew failed: {str(e)}")
            return image
    
    def _binarize(self, image: np.ndarray) -> np.ndarray:
        """Convert to binary (black and white)"""
        if len(image.shape) == 3:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        else:
            gray = image
        
        # Adaptive thresholding for uneven lighting
        binary = cv2.adaptiveThreshold(
            gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY, 11, 2
        )
        
        return binary
    
    def _remove_borders(self, image: np.ndarray) -> np.ndarray:
        """Remove borders from scanned documents"""
        try:
            # Get image dimensions
            h, w = image.shape[:2]
            
            # Find all contours
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            # Threshold
            thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
            
            # Find contours
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            if not contours:
                return image
            
            # Get bounding box of all content
            all_contours = np.vstack(contours)
            x, y, w_ct, h_ct = cv2.boundingRect(all_contours)
            
            # Add small padding
            padding = 10
            x = max(0, x - padding)
            y = max(0, y - padding)
            w_ct = min(w - x, w_ct + 2 * padding)
            h_ct = min(h - y, h_ct + 2 * padding)
            
            # Crop image
            cropped = image[y:y+h_ct, x:x+w_ct]
            
            return cropped
        
        except Exception as e:
            logger.warning(f"Border removal failed: {str(e)}")
            return image
    
    def _resize_to_dpi(self, image: np.ndarray, target_dpi: int) -> np.ndarray:
        """Resize image to target DPI for better OCR"""
        try:
            # Current DPI estimation (default 72 for screen images)
            current_dpi = 72
            
            # Calculate scale factor
            scale_factor = target_dpi / current_dpi
            
            if scale_factor > 1:
                # Only upscale if target DPI is higher
                new_width = int(image.shape[1] * scale_factor)
                new_height = int(image.shape[0] * scale_factor)
                resized = cv2.resize(image, (new_width, new_height), 
                                     interpolation=cv2.INTER_CUBIC)
                return resized
            
            return image
        
        except Exception as e:
            logger.warning(f"Resize failed: {str(e)}")
            return image
    
    async def extract_quality_metrics(self, image_data: Union[bytes, str, Path]) -> Dict[str, Any]:
        """
        Analyze image quality for OCR
        
        Returns:
            Dictionary with quality metrics (blur, brightness, contrast, etc.)
        """
        try:
            image = self._load_image(image_data)
            
            # Convert to grayscale
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image
            
            # Calculate metrics
            metrics = {
                "width": image.shape[1],
                "height": image.shape[0],
                "is_color": len(image.shape) == 3,
                "channels": image.shape[2] if len(image.shape) == 3 else 1,
                "blur_score": self._calculate_blur_score(gray),
                "brightness": float(np.mean(gray)),
                "contrast": float(np.std(gray)),
                "noise_level": self._calculate_noise_level(gray)
            }
            
            # Quality assessment
            metrics["quality_score"] = self._calculate_quality_score(metrics)
            metrics["ocr_readiness"] = "good" if metrics["quality_score"] > 0.7 else "poor"
            
            return metrics
        
        except Exception as e:
            logger.error(f"Quality metrics extraction failed: {str(e)}")
            return {"error": str(e), "quality_score": 0.0}
    
    def _calculate_blur_score(self, image: np.ndarray) -> float:
        """Calculate blur score using Laplacian variance"""
        laplacian = cv2.Laplacian(image, cv2.CV_64F)
        variance = laplacian.var()
        # Normalize to 0-1 range (higher is sharper)
        return min(variance / 500.0, 1.0)
    
    def _calculate_noise_level(self, image: np.ndarray) -> float:
        """Estimate noise level"""
        # Use median filter to estimate noise
        denoised = cv2.medianBlur(image, 5)
        noise = np.abs(image.astype(float) - denoised.astype(float))
        noise_level = np.mean(noise) / 255.0
        return min(noise_level, 1.0)
    
    def _calculate_quality_score(self, metrics: Dict[str, Any]) -> float:
        """Calculate overall image quality score (0-1)"""
        score = 1.0
        
        # Penalize blur
        if metrics["blur_score"] < 0.3:
            score -= 0.3
        elif metrics["blur_score"] < 0.5:
            score -= 0.15
        
        # Penalize extreme brightness
        if metrics["brightness"] < 50 or metrics["brightness"] > 200:
            score -= 0.2
        elif metrics["brightness"] < 80 or metrics["brightness"] > 180:
            score -= 0.1
        
        # Penalize low contrast
        if metrics["contrast"] < 30:
            score -= 0.2
        elif metrics["contrast"] < 50:
            score -= 0.1
        
        # Penalize high noise
        if metrics["noise_level"] > 0.2:
            score -= 0.2
        elif metrics["noise_level"] > 0.1:
            score -= 0.1
        
        return max(0, min(1, score))
    
    def save_preprocessed_image(self, image: np.ndarray, output_path: Union[str, Path]) -> bool:
        """Save preprocessed image to disk"""
        try:
            cv2.imwrite(str(output_path), image)
            return True
        except Exception as e:
            logger.error(f"Failed to save preprocessed image: {str(e)}")
            return False