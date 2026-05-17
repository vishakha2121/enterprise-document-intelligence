"""
Invoice Data Extractor
Extracts structured data from invoice documents
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from decimal import Decimal
import json

from app.core.nlp.ner_extractor import NERExtractor
from app.core.nlp.text_cleaner import TextCleaner
from app.config import settings

logger = logging.getLogger(__name__)

class InvoiceExtractor:
    """
    Specialized extractor for invoice documents
    Extracts: invoice number, dates, amounts, vendor/customer info, line items
    """
    
    def __init__(self):
        """Initialize invoice extractor"""
        self.ner_extractor = NERExtractor()
        self.text_cleaner = TextCleaner()
        
        # Regex patterns for invoice extraction
        self.patterns = {
            "invoice_number": [
                r'(?:invoice|inv|bill|invoice no|invoice number|inv no)[\s:.#-]+([A-Z0-9\-/]+)',
                r'(?:#|no\.?)[\s:]*([A-Z0-9\-/]{4,20})',
                r'\b(?:INV|INVOICE)[\-]?\d{4,}\b',
                r'\b(?:BILL|BILLING)[\-]?\d{4,}\b'
            ],
            "po_number": [
                r'(?:po|purchase order|order no|po number)[\s:.#-]+([A-Z0-9\-/]+)',
                r'(?:PO)[\-]?\d{4,}\b'
            ],
            "date": [
                r'(?:date|invoice date|bill date|issue date)[\s:]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                r'(?:date|invoice date|bill date|issue date)[\s:]+(\d{4}-\d{2}-\d{2})',
                r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{4})\b',
                r'\b(\d{4}-\d{2}-\d{2})\b'
            ],
            "due_date": [
                r'(?:due date|payment due|pay by|due on)[\s:]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                r'(?:due date|payment due|pay by|due on)[\s:]+(\d{4}-\d{2}-\d{2})'
            ],
            "subtotal": [
                r'(?:subtotal|sub total|sub-total)[\s:]+(?:₹|Rs\.?|\$|€)?[\s]*(\d+(?:[,.]\d+)?)',
                r'(?:subtotal|sub total)[\s:]+(\d+(?:[,.]\d+)?)'
            ],
            "tax_amount": [
                r'(?:tax|gst|vat|tax amount|gst amount)[\s:]+(?:₹|Rs\.?|\$|€)?[\s]*(\d+(?:[,.]\d+)?)',
                r'(?:tax|gst|vat)[\s:]+(\d+(?:[,.]\d+)?)'
            ],
            "tax_rate": [
                r'(?:tax|gst|vat)\s+(\d+(?:\.\d+)?)\s?%',
                r'(\d+(?:\.\d+)?)\s?%\s+(?:gst|vat|tax)'
            ],
            "total_amount": [
                r'(?:total|grand total|amount due|balance due|invoice total)[\s:]+(?:₹|Rs\.?|\$|€)?[\s]*(\d+(?:[,.]\d+)?)',
                r'(?:total|grand total)[\s:]+(\d+(?:[,.]\d+)?)'
            ],
            "currency": [
                r'(?:₹|Rs\.?|INR)',
                r'(?:\$|USD)',
                r'(?:€|EUR)',
                r'(?:£|GBP)'
            ],
            "vendor_gst": [
                r'(?:vendor|seller|supplier)\s+gst[\s:]*([A-Z0-9]{15})',
                r'gst(?:in|number)?[\s:]*([A-Z0-9]{15})'
            ],
            "customer_gst": [
                r'(?:customer|buyer|client)\s+gst[\s:]*([A-Z0-9]{15})'
            ],
            "bank_account": [
                r'(?:bank account|account no|a/c no)[\s:]+([0-9]{9,18})',
                r'(?:IFSC|IFSC Code)[\s:]+([A-Z0-9]{11})'
            ]
        }
        
        # Line item patterns
        self.line_item_pattern = re.compile(
            r'(?:^|\n)(\d+)[\s.]+(.+?)[\s]+(\d+(?:[,.]\d+)?)[\s]+(?:₹|Rs\.?|\$)?[\s]*(\d+(?:[,.]\d+)?)',
            re.MULTILINE
        )
        
        logger.info("Invoice Extractor initialized")
    
    async def extract(self, text: str, ocr_text: Optional[str] = None) -> Dict[str, Any]:
        """
        Extract all invoice data from text
        
        Args:
            text: Document text content
            ocr_text: Raw OCR text (if different from cleaned text)
        
        Returns:
            Structured invoice data
        """
        # Clean text
        cleaned_text = self.text_cleaner.clean_text(text, lowercase=False)
        
        # Use NER for additional extraction
        ner_result = await self.ner_extractor.extract_entities(cleaned_text)
        
        # Extract using regex patterns
        extracted = {
            "invoice_number": None,
            "po_number": None,
            "invoice_date": None,
            "due_date": None,
            "vendor_name": None,
            "vendor_address": None,
            "vendor_gst": None,
            "customer_name": None,
            "customer_address": None,
            "customer_gst": None,
            "subtotal": None,
            "tax_amount": None,
            "tax_rate": None,
            "total_amount": None,
            "currency": None,
            "payment_terms": None,
            "bank_details": {},
            "line_items": [],
            "additional_notes": None,
            "confidence_scores": {}
        }
        
        # Extract with regex patterns
        for field, patterns in self.patterns.items():
            for pattern in patterns:
                match = re.search(pattern, cleaned_text, re.IGNORECASE)
                if match:
                    value = match.group(1) if len(match.groups()) > 0 else match.group(0)
                    if field in ["subtotal", "tax_amount", "total_amount"]:
                        value = self._parse_amount(value)
                    extracted[field] = value
                    extracted["confidence_scores"][field] = 0.85
                    break
        
        # Extract from NER results
        if ner_result.get("success"):
            key_fields = ner_result.get("key_fields", {})
            extracted["vendor_name"] = extracted["vendor_name"] or key_fields.get("vendor_name")
            extracted["customer_name"] = extracted["customer_name"] or key_fields.get("customer_name")
            extracted["total_amount"] = extracted["total_amount"] or key_fields.get("total_amount")
            extracted["invoice_date"] = extracted["invoice_date"] or key_fields.get("date")
        
        # Extract line items
        extracted["line_items"] = self._extract_line_items(cleaned_text)
        
        # Extract vendor/customer names using NER
        if not extracted["vendor_name"]:
            extracted["vendor_name"] = self._extract_entity_by_type(ner_result, "organization", 0)
        if not extracted["customer_name"]:
            extracted["customer_name"] = self._extract_entity_by_type(ner_result, "person_name", 0) or \
                                        self._extract_entity_by_type(ner_result, "organization", 1)
        
        # Validate calculations
        extracted["validation"] = self._validate_calculations(extracted)
        
        # Calculate overall confidence
        extracted["overall_confidence"] = self._calculate_overall_confidence(extracted)
        
        # Extract payment terms
        extracted["payment_terms"] = self._extract_payment_terms(cleaned_text)
        
        # Extract bank details
        extracted["bank_details"] = self._extract_bank_details(cleaned_text)
        
        return extracted
    
    def _parse_amount(self, amount_str: str) -> float:
        """Parse amount string to float"""
        if not amount_str:
            return 0.0
        
        # Remove currency symbols and spaces
        cleaned = re.sub(r'[^\d,.-]', '', str(amount_str))
        
        # Handle comma as decimal or thousand separator
        if ',' in cleaned and '.' in cleaned:
            # Indian format: 1,23,456.78
            cleaned = cleaned.replace(',', '')
        elif ',' in cleaned:
            # Check if comma is decimal separator (e.g., "1,23" vs "1,234")
            parts = cleaned.split(',')
            if len(parts[-1]) == 2:
                # Comma is decimal separator
                cleaned = cleaned.replace(',', '.')
            else:
                # Comma is thousand separator
                cleaned = cleaned.replace(',', '')
        
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
    
    def _extract_line_items(self, text: str) -> List[Dict[str, Any]]:
        """Extract line items from invoice"""
        line_items = []
        
        # Try to find line items in table format
        lines = text.split('\n')
        in_line_items = False
        current_item = {}
        
        for line in lines:
            # Check for line item pattern
            match = self.line_item_pattern.search(line)
            if match:
                item = {
                    "serial_no": match.group(1),
                    "description": match.group(2).strip(),
                    "quantity": self._parse_amount(match.group(3)),
                    "unit_price": self._parse_amount(match.group(4)) / self._parse_amount(match.group(3)) if self._parse_amount(match.group(3)) > 0 else 0,
                    "amount": self._parse_amount(match.group(4))
                }
                line_items.append(item)
                in_line_items = True
            elif in_line_items and len(line.strip()) > 5 and not any(c.isdigit() for c in line[:5]):
                # Continue description for previous item
                if line_items:
                    line_items[-1]["description"] += " " + line.strip()
        
        return line_items
    
    def _extract_entity_by_type(self, ner_result: Dict, entity_type: str, index: int = 0) -> Optional[str]:
        """Extract specific entity type from NER results"""
        entities = ner_result.get("entities", {}).get(entity_type, [])
        if entities and len(entities) > index:
            return entities[index].get("text")
        return None
    
    def _validate_calculations(self, extracted: Dict) -> Dict[str, Any]:
        """Validate invoice calculations"""
        validation = {
            "is_valid": True,
            "issues": [],
            "warnings": []
        }
        
        subtotal = extracted.get("subtotal", 0)
        tax = extracted.get("tax_amount", 0)
        total = extracted.get("total_amount", 0)
        tax_rate = extracted.get("tax_rate", 0)
        
        # Check subtotal + tax = total
        if subtotal and tax and total:
            expected_total = subtotal + tax
            if abs(total - expected_total) > 0.01:
                validation["is_valid"] = False
                validation["issues"].append({
                    "type": "calculation_mismatch",
                    "message": f"Total ({total}) does not equal subtotal + tax ({subtotal} + {tax} = {expected_total})",
                    "expected": expected_total,
                    "actual": total
                })
        
        # Check tax calculation
        if subtotal and tax_rate and not tax:
            expected_tax = subtotal * (tax_rate / 100)
            if extracted.get("tax_amount"):
                if abs(extracted["tax_amount"] - expected_tax) > 0.01:
                    validation["warnings"].append({
                        "type": "tax_mismatch",
                        "message": f"Tax amount ({extracted['tax_amount']}) does not match {tax_rate}% of subtotal ({expected_tax})"
                    })
        
        # Check line items sum
        line_items = extracted.get("line_items", [])
        if line_items:
            line_items_total = sum(item.get("amount", 0) for item in line_items)
            if subtotal and abs(line_items_total - subtotal) > 0.01:
                validation["warnings"].append({
                    "type": "line_items_mismatch",
                    "message": f"Sum of line items ({line_items_total}) does not match subtotal ({subtotal})"
                })
        
        return validation
    
    def _calculate_overall_confidence(self, extracted: Dict) -> float:
        """Calculate overall confidence score for extraction"""
        confidence_scores = extracted.get("confidence_scores", {})
        
        if not confidence_scores:
            return 0.5
        
        # Weight critical fields higher
        weights = {
            "invoice_number": 0.2,
            "total_amount": 0.2,
            "invoice_date": 0.15,
            "vendor_name": 0.15,
            "customer_name": 0.1,
            "subtotal": 0.1,
            "tax_amount": 0.05,
            "due_date": 0.05
        }
        
        total_weighted_score = 0
        total_weight = 0
        
        for field, weight in weights.items():
            if field in confidence_scores:
                total_weighted_score += confidence_scores[field] * weight
                total_weight += weight
            elif extracted.get(field):
                # Field found but no confidence score
                total_weighted_score += 0.7 * weight
                total_weight += weight
        
        if total_weight > 0:
            return total_weighted_score / total_weight
        
        return 0.5
    
    def _extract_payment_terms(self, text: str) -> Optional[str]:
        """Extract payment terms from invoice"""
        patterns = [
            r'(?:payment terms|terms|payment due)[\s:]+([^.\n]+)',
            r'(?:net|due in)\s+(\d+\s+days?)',
            r'(?:payment)\s+(\d+\%?\s+\d+\s+days?)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return None
    
    def _extract_bank_details(self, text: str) -> Dict[str, str]:
        """Extract bank account details"""
        bank_details = {}
        
        # Extract account number
        acc_match = re.search(r'(?:account|a/c|acct)[\s:]+([0-9]{9,18})', text, re.IGNORECASE)
        if acc_match:
            bank_details["account_number"] = acc_match.group(1)
        
        # Extract IFSC code
        ifsc_match = re.search(r'(?:IFSC|IFSC Code)[\s:]+([A-Z0-9]{11})', text, re.IGNORECASE)
        if ifsc_match:
            bank_details["ifsc_code"] = ifsc_match.group(1)
        
        # Extract bank name
        bank_match = re.search(r'(?:bank|bank name)[\s:]+([A-Za-z\s]+)', text, re.IGNORECASE)
        if bank_match:
            bank_details["bank_name"] = bank_match.group(1).strip()
        
        return bank_details
    
    def to_json(self, extracted_data: Dict[str, Any]) -> str:
        """Convert extracted data to JSON string"""
        return json.dumps(extracted_data, indent=2, default=str)
    
    def to_erp_format(self, extracted_data: Dict[str, Any], erp_system: str = "generic") -> Dict[str, Any]:
        """Convert extracted data to ERP-specific format"""
        erp_mapping = {
            "generic": {
                "document_type": "invoice",
                "document_number": "invoice_number",
                "document_date": "invoice_date",
                "due_date": "due_date",
                "vendor": "vendor_name",
                "customer": "customer_name",
                "subtotal": "subtotal",
                "tax": "tax_amount",
                "total": "total_amount"
            },
            "sap": {
                "VBELN": "invoice_number",
                "FKDAT": "invoice_date",
                "NETWR": "total_amount",
                "KUNNR": "customer_name"
            },
            "oracle": {
                "InvoiceNum": "invoice_number",
                "InvoiceDate": "invoice_date",
                "InvoiceAmount": "total_amount"
            },
            "quickbooks": {
                "InvoiceNumber": "invoice_number",
                "DueDate": "due_date",
                "Total": "total_amount"
            }
        }
        
        mapping = erp_mapping.get(erp_system.lower(), erp_mapping["generic"])
        
        erp_data = {"type": "invoice", "system": erp_system}
        
        for erp_field, source_field in mapping.items():
            if source_field in extracted_data:
                erp_data[erp_field] = extracted_data[source_field]
        
        return erp_data