"""
Form Data Extractor
Extracts structured data from form documents (applications, registrations, etc.)
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
import json

from app.core.nlp.ner_extractor import NERExtractor
from app.core.nlp.text_cleaner import TextCleaner

logger = logging.getLogger(__name__)

class FormExtractor:
    """
    Specialized extractor for form documents
    Extracts: field-value pairs, applicant info, responses
    """
    
    def __init__(self):
        """Initialize form extractor"""
        self.ner_extractor = NERExtractor()
        self.text_cleaner = TextCleaner()
        
        # Form field patterns
        self.field_patterns = {
            "name": [
                r'(?:full name|name of applicant|applicant name)[\s:]+([^\n]+)',
                r'(?:name)[\s:]+([A-Za-z\s.]+)(?:\n|$)'
            ],
            "email": [
                r'(?:email|e-mail|email address)[\s:]+([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})'
            ],
            "phone": [
                r'(?:phone|mobile|contact number|telephone)[\s:]+(\+?\d[\d\s-]{8,}\d)'
            ],
            "address": [
                r'(?:address|residential address|postal address)[\s:]+([^\n]+(?:\n[^\n]+){0,3})'
            ],
            "date_of_birth": [
                r'(?:date of birth|dob|birth date)[\s:]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
            ],
            "organization": [
                r'(?:organization|company|institution|employer)[\s:]+([^\n]+)'
            ],
            "designation": [
                r'(?:designation|position|job title|role)[\s:]+([^\n]+)'
            ]
        }
        
        # Checkbox/radio patterns
        self.checkbox_patterns = {
            "yes_no": r'(?:yes|no|true|false)[\s]*[x✓]?',
            "selected_option": r'(?:[x✓])\s*([^\n]+)',
            "checkbox_field": r'\[\s*[x✓]\s*\]\s*([^\n]+)'
        }
        
        logger.info("Form Extractor initialized")
    
    async def extract(self, text: str, form_schema: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Extract form data from text
        
        Args:
            text: Form document text
            form_schema: Optional schema defining expected fields
        
        Returns:
            Structured form data
        """
        cleaned_text = self.text_cleaner.clean_text(text, lowercase=False)
        
        # Use NER for entity extraction
        ner_result = await self.ner_extractor.extract_entities(cleaned_text)
        
        # Extract using regex patterns
        extracted = {
            "form_id": None,
            "submission_date": None,
            "applicant_info": {},
            "responses": {},
            "checkboxes": {},
            "declarations": [],
            "signatures": [],
            "attachments": [],
            "form_type": None,
            "confidence_scores": {}
        }
        
        # Extract form ID
        form_id_match = re.search(r'(?:form|application)[\s:.#-]+([A-Z0-9\-/]+)', cleaned_text, re.IGNORECASE)
        if form_id_match:
            extracted["form_id"] = form_id_match.group(1)
        
        # Extract submission date
        date_match = re.search(r'(?:submission date|date of submission|date)[\s:]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', cleaned_text, re.IGNORECASE)
        if date_match:
            extracted["submission_date"] = date_match.group(1)
        
        # Extract fields using patterns
        for field, patterns in self.field_patterns.items():
            for pattern in patterns:
                match = re.search(pattern, cleaned_text, re.IGNORECASE)
                if match:
                    value = match.group(1).strip()
                    extracted["applicant_info"][field] = value
                    extracted["confidence_scores"][field] = 0.85
                    break
        
        # Extract from NER results
        if ner_result.get("success"):
            key_fields = ner_result.get("key_fields", {})
            if not extracted["applicant_info"].get("name"):
                extracted["applicant_info"]["name"] = key_fields.get("person_name")
            if not extracted["applicant_info"].get("email"):
                extracted["applicant_info"]["email"] = key_fields.get("email")
        
        # Extract field-value pairs from form
        extracted["responses"] = self._extract_field_value_pairs(cleaned_text)
        
        # Extract checkboxes
        extracted["checkboxes"] = self._extract_checkboxes(cleaned_text)
        
        # Extract declarations
        extracted["declarations"] = self._extract_declarations(cleaned_text)
        
        # Extract signatures
        extracted["signatures"] = self._extract_signatures(cleaned_text)
        
        # Determine form type
        extracted["form_type"] = self._determine_form_type(cleaned_text)
        
        # Apply schema validation if provided
        if form_schema:
            extracted["validation"] = self._validate_against_schema(extracted, form_schema)
        
        # Calculate overall confidence
        extracted["overall_confidence"] = self._calculate_overall_confidence(extracted)
        
        return extracted
    
    def _extract_field_value_pairs(self, text: str) -> Dict[str, str]:
        """Extract field-value pairs from form"""
        responses = {}
        
        # Common field patterns
        field_patterns = [
            r'([A-Z][a-z]+(?: [A-Z][a-z]+)*)[\s:]+([^\n]+)',
            r'(\w+(?:\s+\w+){0,3})[\s:]+([^:\n]+)'
        ]
        
        lines = text.split('\n')
        for line in lines:
            for pattern in field_patterns:
                match = re.match(pattern, line.strip())
                if match and len(match.group(1)) > 2 and len(match.group(2)) > 1:
                    field = match.group(1).strip().lower().replace(' ', '_')
                    value = match.group(2).strip()
                    if len(value) < 100:  # Avoid very long values
                        responses[field] = value
                    break
        
        return responses
    
    def _extract_checkboxes(self, text: str) -> Dict[str, Any]:
        """Extract checkbox selections"""
        checkboxes = {}
        
        # Look for marked checkboxes
        for pattern in self.checkbox_patterns.values():
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                if isinstance(match, tuple):
                    match = match[0]
                checkboxes[match.strip()] = True
        
        # Look for checkbox options
        checkbox_options = re.findall(r'\[[ x]\]\s*([^\n]+)', text, re.IGNORECASE)
        for option in checkbox_options:
            is_checked = '[x]' in text.lower() or '[✓]' in text
            checkboxes[option.strip()] = is_checked
        
        return checkboxes
    
    def _extract_declarations(self, text: str) -> List[Dict[str, Any]]:
        """Extract declarations and affirmations"""
        declarations = []
        
        # Look for declaration statements
        declaration_patterns = [
            r'(?:I hereby declare|I certify|I confirm)[\s:]+([^.\n]+[.])',
            r'(?:declaration|affirmation)[\s:]+([^.\n]+[.])'
        ]
        
        for pattern in declaration_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                declarations.append({
                    "text": match.strip(),
                    "agreed": "agree" in text.lower() or "accept" in text.lower()
                })
        
        return declarations
    
    def _extract_signatures(self, text: str) -> List[Dict[str, str]]:
        """Extract signature information"""
        signatures = []
        
        # Look for signature fields
        signature_patterns = [
            r'(?:signature|signed by|electronic signature)[\s:]+([^\n]+)',
            r'(?:applicant signature)[\s:]+([^\n]+)'
        ]
        
        for pattern in signature_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                signatures.append({
                    "signer": match.strip(),
                    "date": None,
                    "type": "digital" if "digital" in match.lower() else "wet"
                })
        
        return signatures
    
    def _determine_form_type(self, text: str) -> str:
        """Determine the type of form"""
        text_lower = text.lower()
        
        form_types = {
            "application": ["application", "apply", "applicant"],
            "registration": ["registration", "register", "sign up"],
            "feedback": ["feedback", "suggestion", "complaint"],
            "survey": ["survey", "questionnaire", "poll"],
            "order": ["order form", "purchase", "buy"],
            "contact": ["contact us", "inquiry", "query"]
        }
        
        for form_type, keywords in form_types.items():
            if any(keyword in text_lower for keyword in keywords):
                return form_type
        
        return "general"
    
    def _validate_against_schema(self, extracted: Dict, schema: Dict) -> Dict[str, Any]:
        """Validate extracted data against schema"""
        validation = {
            "valid": True,
            "missing_fields": [],
            "invalid_fields": []
        }
        
        required_fields = schema.get("required_fields", [])
        
        for field in required_fields:
            if field not in extracted.get("responses", {}) and field not in extracted.get("applicant_info", {}):
                validation["missing_fields"].append(field)
                validation["valid"] = False
        
        return validation
    
    def _calculate_overall_confidence(self, extracted: Dict) -> float:
        """Calculate overall confidence score"""
        confidence_scores = extracted.get("confidence_scores", {})
        
        if not confidence_scores:
            return 0.5
        
        # Weight critical fields
        weights = {
            "name": 0.2,
            "email": 0.15,
            "phone": 0.15,
            "address": 0.1,
            "submission_date": 0.1
        }
        
        total_weighted = 0
        total_weight = 0
        
        for field, weight in weights.items():
            if field in confidence_scores:
                total_weighted += confidence_scores[field] * weight
                total_weight += weight
            elif extracted.get("applicant_info", {}).get(field):
                total_weighted += 0.7 * weight
                total_weight += weight
        
        # Add bonus for number of responses extracted
        response_count = len(extracted.get("responses", {}))
        if response_count > 5:
            total_weighted += 0.1
        elif response_count > 10:
            total_weighted += 0.15
        
        return min(total_weighted / total_weight if total_weight > 0 else 0.6, 1.0)
    
    def to_json(self, extracted_data: Dict[str, Any]) -> str:
        """Convert extracted data to JSON string"""
        return json.dumps(extracted_data, indent=2, default=str)
    
    def to_csv(self, extracted_data: Dict[str, Any]) -> str:
        """Convert extracted data to CSV format"""
        rows = []
        
        # Flatten data
        flat_data = {}
        
        # Add applicant info
        for key, value in extracted_data.get("applicant_info", {}).items():
            flat_data[key] = value
        
        # Add responses
        for key, value in extracted_data.get("responses", {}).items():
            flat_data[key] = value
        
        # Create CSV
        if flat_data:
            headers = list(flat_data.keys())
            rows.append(','.join(headers))
            rows.append(','.join(str(flat_data.get(h, '')) for h in headers))
        
        return '\n'.join(rows)