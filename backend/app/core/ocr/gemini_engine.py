"""
Gemini AI OCR Engine
Advanced OCR using Google Gemini API for complex documents
"""

import google.generativeai as genai
from PIL import Image
import io
import base64
import logging
from typing import Union, Dict, Any, Optional, List
from pathlib import Path
import json
import asyncio
import time

from app.config import settings

logger = logging.getLogger(__name__)

class GeminiEngine:
    """
    Gemini API-based OCR engine for advanced document processing
    Supports complex layouts, handwriting, and multilingual text
    """
    
    def __init__(self):
        """Initialize Gemini API client"""
        self.api_key = settings.GEMINI_API_KEY
        self.model_name = "gemini-pro-vision"
        self.is_available = False
        
        if self.api_key:
            try:
                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel(self.model_name)
                self.is_available = True
                logger.info("Gemini OCR Engine initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Gemini: {str(e)}")
        else:
            logger.warning("Gemini API key not found. Gemini OCR disabled.")
    
    async def extract_text(
        self,
        image_data: Union[bytes, str, Path, Image.Image],
        prompt: Optional[str] = None,
        extract_structured: bool = True
    ) -> Dict[str, Any]:
        """
        Extract text from image using Gemini Vision API
        
        Args:
            image_data: Image data (bytes, path, or PIL Image)
            prompt: Custom prompt for extraction
            extract_structured: Extract structured data (JSON format)
        
        Returns:
            Dictionary with extracted text and structured data
        """
        if not self.is_available:
            return {
                "success": False,
                "error": "Gemini API not available. Check API key.",
                "text": "",
                "engine": "gemini"
            }
        
        start_time = time.time()
        
        try:
            # Load and prepare image
            image = self._prepare_image(image_data)
            
            # Build prompt
            if not prompt:
                if extract_structured:
                    prompt = self._get_structured_extraction_prompt()
                else:
                    prompt = self._get_basic_extraction_prompt()
            
            # Call Gemini API
            response = await self._call_gemini_api(image, prompt)
            
            # Parse response
            if extract_structured:
                structured_data = self._parse_structured_response(response.text)
                extracted_text = structured_data.get("full_text", response.text)
            else:
                structured_data = {}
                extracted_text = response.text
            
            processing_time = (time.time() - start_time) * 1000
            
            return {
                "success": True,
                "text": extracted_text,
                "structured_data": structured_data if extract_structured else None,
                "raw_response": response.text,
                "processing_time_ms": processing_time,
                "engine": "gemini",
                "model": self.model_name
            }
        
        except Exception as e:
            logger.error(f"Gemini OCR failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "text": "",
                "processing_time_ms": (time.time() - start_time) * 1000,
                "engine": "gemini"
            }
    
    async def analyze_document(
        self,
        image_data: Union[bytes, str, Path],
        analysis_type: str = "full"
    ) -> Dict[str, Any]:
        """
        Comprehensive document analysis with Gemini
        
        Args:
            image_data: Document image
            analysis_type: Type of analysis (full, summary, fields, fraud)
        
        Returns:
            Comprehensive analysis results
        """
        if not self.is_available:
            return {"success": False, "error": "Gemini API not available"}
        
        prompts = {
            "full": """
            Analyze this document thoroughly and provide:
            1. Document type (invoice, contract, form, receipt, etc.)
            2. Key information extracted (dates, amounts, names, IDs)
            3. Summary of content
            4. Any unusual or suspicious elements
            5. Overall document quality
            Return as JSON with fields: document_type, key_info, summary, suspicious_elements, quality_score
            """,
            
            "summary": "Provide a concise 2-3 sentence summary of this document.",
            
            "fields": """
            Extract all key fields from this document as a JSON object.
            Common fields include: invoice_number, date, total_amount, vendor_name, customer_name.
            Return ONLY valid JSON.
            """,
            
            "fraud": """
            Analyze this document for potential fraud indicators:
            - Check for tampering or alterations
            - Verify logical consistency (dates, amounts)
            - Look for suspicious patterns
            - Identify any red flags
            Return as JSON with fields: is_suspicious, confidence, reasons, red_flags
            """
        }
        
        prompt = prompts.get(analysis_type, prompts["full"])
        
        result = await self.extract_text(image_data, prompt=prompt, extract_structured=True)
        
        if result["success"] and result.get("structured_data"):
            return {
                "success": True,
                "analysis_type": analysis_type,
                "results": result["structured_data"],
                "confidence": 0.85,  # Gemini doesn't provide confidence
                "engine": "gemini"
            }
        
        return result
    
    async def extract_table_data(
        self,
        image_data: Union[bytes, str, Path]
    ) -> Dict[str, Any]:
        """
        Extract structured table data from documents
        
        Args:
            image_data: Document image containing tables
        
        Returns:
            Extracted table data as structured JSON
        """
        prompt = """
        Extract all table data from this document.
        Identify rows, columns, and cell values.
        Return as JSON with structure:
        {
            "tables": [
                {
                    "headers": ["col1", "col2", ...],
                    "rows": [
                        ["val1", "val2", ...],
                        ...
                    ],
                    "total_rows": int,
                    "total_columns": int
                }
            ]
        }
        """
        
        result = await self.extract_text(image_data, prompt=prompt, extract_structured=True)
        
        if result["success"] and result.get("structured_data"):
            return {
                "success": True,
                "tables": result["structured_data"].get("tables", []),
                "engine": "gemini"
            }
        
        return {"success": False, "tables": [], "error": "Failed to extract tables"}
    
    async def extract_handwriting(
        self,
        image_data: Union[bytes, str, Path]
    ) -> Dict[str, Any]:
        """
        Specialized extraction for handwritten content
        """
        prompt = """
        Extract all handwritten text from this document.
        Handwritten content may include: signatures, notes, filled form fields.
        Return as JSON:
        {
            "handwritten_text": "extracted text",
            "handwritten_fields": {"field_name": "value"},
            "signatures_detected": ["signer1", "signer2"],
            "confidence": float
        }
        """
        
        return await self.extract_text(image_data, prompt=prompt, extract_structured=True)
    
    def _prepare_image(self, image_data: Union[bytes, str, Path, Image.Image]) -> Image.Image:
        """Prepare image for Gemini API"""
        if isinstance(image_data, bytes):
            return Image.open(io.BytesIO(image_data))
        elif isinstance(image_data, (str, Path)):
            return Image.open(str(image_data))
        elif isinstance(image_data, Image.Image):
            return image_data
        else:
            raise ValueError(f"Unsupported image type: {type(image_data)}")
    
    def _get_basic_extraction_prompt(self) -> str:
        """Get basic OCR extraction prompt"""
        return """
        Extract all text from this document exactly as it appears.
        Preserve formatting, line breaks, and spacing where possible.
        Return ONLY the extracted text without any additional commentary.
        """
    
    def _get_structured_extraction_prompt(self) -> str:
        """Get structured extraction prompt for key information"""
        return """
        Extract text and key information from this document.
        Return a JSON object with:
        {
            "full_text": "Complete extracted text",
            "document_type": "Type of document",
            "key_fields": {
                "date": "extracted date",
                "amount": "extracted amount",
                "invoice_number": "invoice/reference number",
                "vendor": "sender/company name",
                "customer": "receiver/client name",
                "description": "document description"
            },
            "line_items": [],
            "total_amount": null,
            "currency": null
        }
        If a field is not found, use null.
        """
    
    async def _call_gemini_api(self, image: Image.Image, prompt: str) -> Any:
        """
        Call Gemini API asynchronously
        """
        try:
            # Run in thread pool (Gemini SDK is synchronous)
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.model.generate_content([prompt, image])
            )
            return response
        except Exception as e:
            logger.error(f"Gemini API call failed: {str(e)}")
            raise
    
    def _parse_structured_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Gemini response into structured data"""
        try:
            # Try to extract JSON from response
            # Gemini might wrap JSON in markdown code blocks
            if "```json" in response_text:
                json_str = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                json_str = response_text.split("```")[1].split("```")[0]
            else:
                json_str = response_text
            
            # Parse JSON
            data = json.loads(json_str.strip())
            return data
        
        except json.JSONDecodeError:
            # If not valid JSON, return raw text
            return {"full_text": response_text, "parse_error": True}
    
    def is_available(self) -> bool:
        """Check if Gemini API is available"""
        return self.is_available