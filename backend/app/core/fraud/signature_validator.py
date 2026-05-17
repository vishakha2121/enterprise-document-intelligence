"""
Signature Validator
Validates digital signatures and handwritten signatures in documents
"""

import re
import logging
from typing import Dict, Any, Optional, List, Tuple
from pathlib import Path
import hashlib
from datetime import datetime
import base64

logger = logging.getLogger(__name__)

class SignatureValidator:
    """
    Validates signatures in documents
    Supports digital signatures (PDF) and handwritten signature detection
    """
    
    def __init__(self):
        """Initialize signature validator"""
        # Common signature patterns in text
        self.signature_patterns = [
            r'(?:signed|signature|digital signature)[\s:]*([A-Za-z\s]+)',
            r'(?:authorized signatory)[\s:]*([A-Za-z\s]+)',
            r'(?:approved by)[\s:]*([A-Za-z\s]+)',
            r'/s/([A-Za-z\s]+)',  # /s/ signature
            r'\[signed\]',
            r'\(signed\)'
        ]
        
        # Signature keywords
        self.signature_keywords = [
            "signature", "signed", "authorized", "approved",
            "digital signature", "esign", "electronic signature",
            "/s/", "[signed]", "(signed)"
        ]
        
        logger.info("Signature Validator initialized")
    
    async def validate_signature(
        self,
        text: str,
        pdf_data: Optional[bytes] = None,
        expected_signer: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate signature presence and authenticity
        
        Args:
            text: Document text content
            pdf_data: PDF binary data for digital signature extraction
            expected_signer: Expected signer name for verification
        
        Returns:
            Signature validation results
        """
        results = {
            "signature_present": False,
            "signature_type": None,  # digital, handwritten, text
            "signer_name": None,
            "is_valid": False,
            "confidence": 0.0,
            "issues": []
        }
        
        # Check for text-based signatures
        text_signature_result = self._check_text_signatures(text)
        
        # Check PDF digital signatures (if available)
        pdf_signature_result = None
        if pdf_data:
            pdf_signature_result = await self._check_pdf_signatures(pdf_data)
        
        # Combine results
        if pdf_signature_result and pdf_signature_result.get("signature_present"):
            results.update(pdf_signature_result)
            results["signature_type"] = "digital"
        elif text_signature_result.get("signature_present"):
            results.update(text_signature_result)
            results["signature_type"] = "text_based"
        else:
            results["issues"].append("No signature found in document")
        
        # Verify signer name if expected
        if expected_signer and results.get("signer_name"):
            results["signer_match"] = self._verify_signer_name(
                results["signer_name"], expected_signer
            )
            if not results["signer_match"]:
                results["issues"].append(f"Signer name '{results['signer_name']}' does not match expected '{expected_signer}'")
                results["confidence"] *= 0.5
        
        # Overall validity
        results["is_valid"] = (
            results["signature_present"] and
            len(results["issues"]) == 0 and
            results["confidence"] >= 0.7
        )
        
        return results
    
    def _check_text_signatures(self, text: str) -> Dict[str, Any]:
        """Check for text-based signatures"""
        text_lower = text.lower()
        
        result = {
            "signature_present": False,
            "signer_name": None,
            "confidence": 0.0,
            "issues": []
        }
        
        # Check for signature keywords
        signature_found = any(keyword in text_lower for keyword in self.signature_keywords)
        
        if not signature_found:
            result["issues"].append("No signature keywords found")
            return result
        
        # Extract potential signer names
        signer_names = []
        for pattern in self.signature_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                signer_names.extend(matches)
        
        # Clean and deduplicate names
        if signer_names:
            # Take the most common name
            from collections import Counter
            name_counts = Counter([n.strip().title() for n in signer_names if len(n.strip()) > 2])
            if name_counts:
                result["signer_name"] = name_counts.most_common(1)[0][0]
                result["confidence"] = 0.8
                result["signature_present"] = True
            else:
                result["signature_present"] = True
                result["confidence"] = 0.6
        else:
            # Signature keywords found but no name extracted
            result["signature_present"] = True
            result["confidence"] = 0.5
            result["issues"].append("Signature present but signer name not extracted")
        
        return result
    
    async def _check_pdf_signatures(self, pdf_data: bytes) -> Dict[str, Any]:
        """
        Check for digital signatures in PDF
        
        Note: Full PDF signature validation requires PyPDF2 or similar
        This is a simplified version
        """
        result = {
            "signature_present": False,
            "signer_name": None,
            "signature_valid": None,
            "signing_time": None,
            "confidence": 0.0,
            "issues": []
        }
        
        try:
            # Check for signature markers in PDF
            pdf_text = pdf_data[:10000].decode('latin-1', errors='ignore')
            
            # Look for signature dictionaries
            if '/Sig' in pdf_text or '/Signature' in pdf_text:
                result["signature_present"] = True
                result["confidence"] = 0.9
                
                # Extract signer name if available
                name_match = re.search(r'/Name\(([^)]+)\)', pdf_text)
                if name_match:
                    result["signer_name"] = name_match.group(1)
                
                # Check signature validity marker
                if '/V' in pdf_text and '/Type/Sig' in pdf_text:
                    result["signature_valid"] = True
                else:
                    result["issues"].append("Digital signature may be invalid or corrupted")
            
            else:
                result["issues"].append("No digital signature found in PDF")
        
        except Exception as e:
            logger.error(f"PDF signature check failed: {str(e)}")
            result["issues"].append("Could not verify digital signature")
        
        return result
    
    def _verify_signer_name(self, extracted_name: str, expected_name: str) -> bool:
        """Verify if extracted signer name matches expected name"""
        # Normalize names
        extracted_normalized = re.sub(r'[^a-z]', '', extracted_name.lower())
        expected_normalized = re.sub(r'[^a-z]', '', expected_name.lower())
        
        # Check for partial matches
        if extracted_normalized == expected_normalized:
            return True
        
        # Check if one is contained in the other
        if extracted_normalized in expected_normalized or expected_normalized in extracted_normalized:
            return True
        
        # Check first/last name matches
        extracted_parts = extracted_normalized.split()
        expected_parts = expected_normalized.split()
        
        for e_part in extracted_parts:
            for ex_part in expected_parts:
                if e_part == ex_part and len(e_part) > 3:
                    return True
        
        return False
    
    async def detect_handwritten_signature(
        self,
        image_data: bytes
    ) -> Dict[str, Any]:
        """
        Detect handwritten signature in image
        
        Args:
            image_data: Image bytes containing potential signature
        
        Returns:
            Signature detection results
        """
        # Simplified version - in production, use ML model for signature detection
        result = {
            "signature_detected": False,
            "confidence": 0.0,
            "bounding_box": None,
            "issues": []
        }
        
        try:
            # Placeholder for actual signature detection logic
            # This would use computer vision to detect signature-like patterns
            
            # For now, assume no detection
            result["issues"].append("Handwritten signature detection requires CV model")
        
        except Exception as e:
            logger.error(f"Handwritten signature detection failed: {str(e)}")
            result["issues"].append("Failed to detect handwritten signature")
        
        return result
    
    def generate_signature_report(self, validation_result: Dict[str, Any]) -> Dict[str, Any]:
        """Generate signature validation report"""
        return {
            "signature_validated": validation_result.get("is_valid", False),
            "signature_type": validation_result.get("signature_type"),
            "signer_name": validation_result.get("signer_name"),
            "confidence": validation_result.get("confidence", 0),
            "issues": validation_result.get("issues", []),
            "recommendation": self._get_signature_recommendation(validation_result)
        }
    
    def _get_signature_recommendation(self, result: Dict[str, Any]) -> str:
        """Get recommendation based on signature validation"""
        if result.get("is_valid"):
            return "Signature is valid"
        
        if not result.get("signature_present"):
            return "Document missing required signature"
        
        if result.get("issues"):
            return f"Signature issues found: {', '.join(result['issues'][:2])}"
        
        return "Signature requires manual verification"