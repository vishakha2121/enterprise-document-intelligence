"""
Contract Data Extractor
Extracts structured data from legal contract documents
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
import json

from app.core.nlp.ner_extractor import NERExtractor
from app.core.nlp.text_cleaner import TextCleaner

logger = logging.getLogger(__name__)

class ContractExtractor:
    """
    Specialized extractor for legal contract documents
    Extracts: parties, dates, terms, clauses, signatures
    """
    
    def __init__(self):
        """Initialize contract extractor"""
        self.ner_extractor = NERExtractor()
        self.text_cleaner = TextCleaner()
        
        # Contract-specific patterns
        self.patterns = {
            "contract_id": [
                r'(?:contract|agreement|contract no|agreement no)[\s:.#-]+([A-Z0-9\-/]+)',
                r'(?:CT|CONT)[\-]?\d{4,}\b'
            ],
            "contract_date": [
                r'(?:date of (?:contract|agreement)|execution date|signed on)[\s:]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                r'^(?:this agreement is made on|dated)[\s:]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})',
                r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{4})\b'
            ],
            "effective_date": [
                r'(?:effective date|commencement date|start date)[\s:]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
            ],
            "expiry_date": [
                r'(?:expiry date|termination date|end date|expiration)[\s:]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
            ],
            "contract_value": [
                r'(?:contract value|consideration|amount|total value)[\s:]+(?:₹|Rs\.?|\$|€)?[\s]*(\d+(?:[,.]\d+)?)'
            ],
            "currency": [
                r'(?:₹|Rs\.?|INR)', r'(?:\$|USD)', r'(?:€|EUR)'
            ],
            "term_months": [
                r'term[\s:]+(\d+)\s*(?:month|year)s?',
                r'duration[\s:]+(\d+)\s*(?:month|year)s?'
            ]
        }
        
        # Clause patterns
        self.clause_patterns = {
            "termination": r'(?:termination|terminate|end of agreement)[\s\S]{0,200}?(?:\d+\s+days?|notice period)',
            "indemnification": r'(?:indemnify|indemnification|hold harmless)[\s\S]{0,300}?',
            "confidentiality": r'(?:confidential|non-disclosure|nda|trade secret)[\s\S]{0,300}?',
            "governing_law": r'(?:governing law|jurisdiction|applicable law)[\s\S]{0,200}?',
            "dispute_resolution": r'(?:dispute|arbitration|mediation|resolution)[\s\S]{0,300}?',
            "payment_terms": r'(?:payment terms|invoicing|billing)[\s\S]{0,200}?',
            "deliverables": r'(?:deliverables|scope of work|services)[\s\S]{0,300}?'
        }
        
        logger.info("Contract Extractor initialized")
    
    async def extract(self, text: str) -> Dict[str, Any]:
        """
        Extract all contract data from text
        
        Args:
            text: Contract document text
        
        Returns:
            Structured contract data
        """
        cleaned_text = self.text_cleaner.clean_text(text, lowercase=False)
        
        # Use NER for entity extraction
        ner_result = await self.ner_extractor.extract_entities(cleaned_text)
        
        # Extract using regex patterns
        extracted = {
            "contract_id": None,
            "contract_date": None,
            "effective_date": None,
            "expiry_date": None,
            "parties": {
                "first_party": None,
                "second_party": None,
                "additional_parties": []
            },
            "contract_value": None,
            "currency": None,
            "term_months": None,
            "clauses": {},
            "signatures": [],
            "witnesses": [],
            "special_conditions": [],
            "confidence_scores": {}
        }
        
        # Extract with regex
        for field, patterns in self.patterns.items():
            for pattern in patterns:
                match = re.search(pattern, cleaned_text, re.IGNORECASE)
                if match:
                    value = match.group(1) if len(match.groups()) > 0 else match.group(0)
                    if field == "contract_value":
                        value = self._parse_amount(value)
                    elif field == "term_months":
                        value = int(value)
                        if 'year' in match.group(0).lower():
                            value *= 12
                    extracted[field] = value
                    extracted["confidence_scores"][field] = 0.85
                    break
        
        # Extract parties from NER
        extracted["parties"] = self._extract_parties(cleaned_text, ner_result)
        
        # Extract clauses
        extracted["clauses"] = self._extract_clauses(cleaned_text)
        
        # Extract signatures
        extracted["signatures"] = self._extract_signatures(cleaned_text)
        
        # Extract witnesses
        extracted["witnesses"] = self._extract_witnesses(cleaned_text)
        
        # Extract special conditions
        extracted["special_conditions"] = self._extract_special_conditions(cleaned_text)
        
        # Calculate overall confidence
        extracted["overall_confidence"] = self._calculate_overall_confidence(extracted)
        
        return extracted
    
    def _parse_amount(self, amount_str: str) -> float:
        """Parse amount string to float"""
        if not amount_str:
            return 0.0
        
        cleaned = re.sub(r'[^\d,.-]', '', str(amount_str))
        if ',' in cleaned and '.' in cleaned:
            cleaned = cleaned.replace(',', '')
        elif ',' in cleaned:
            parts = cleaned.split(',')
            if len(parts[-1]) == 2:
                cleaned = cleaned.replace(',', '.')
            else:
                cleaned = cleaned.replace(',', '')
        
        try:
            return float(cleaned)
        except ValueError:
            return 0.0
    
    def _extract_parties(self, text: str, ner_result: Dict) -> Dict[str, Any]:
        """Extract party information from contract"""
        parties = {
            "first_party": None,
            "second_party": None,
            "additional_parties": []
        }
        
        # Extract using NER for organizations and persons
        organizations = ner_result.get("entities", {}).get("organization", [])
        persons = ner_result.get("entities", {}).get("person_name", [])
        
        # Look for party markers
        party_patterns = [
            r'(?:between|by and between)[\s:]+([^,]+(?:,?\s+and\s+[^,]+)?)',
            r'(?:first party|party of the first part)[\s:]+([^,\n]+)',
            r'(?:second party|party of the second part)[\s:]+([^,\n]+)'
        ]
        
        party_names = []
        for pattern in party_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                party_names.append(match.group(1).strip())
        
        # Assign parties
        if len(party_names) >= 1:
            parties["first_party"] = party_names[0]
        if len(party_names) >= 2:
            parties["second_party"] = party_names[1]
        
        # Use NER results if regex didn't find
        if not parties["first_party"] and organizations:
            parties["first_party"] = organizations[0].get("text") if organizations else None
        if not parties["second_party"] and len(organizations) > 1:
            parties["second_party"] = organizations[1].get("text")
        elif not parties["second_party"] and persons:
            parties["second_party"] = persons[0].get("text") if persons else None
        
        return parties
    
    def _extract_clauses(self, text: str) -> Dict[str, str]:
        """Extract key clauses from contract"""
        clauses = {}
        
        for clause_name, pattern in self.clause_patterns.items():
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                clause_text = match.group(0).strip()
                # Clean and truncate clause text
                clause_text = re.sub(r'\s+', ' ', clause_text)
                if len(clause_text) > 500:
                    clause_text = clause_text[:500] + "..."
                clauses[clause_name] = clause_text
        
        return clauses
    
    def _extract_signatures(self, text: str) -> List[Dict[str, str]]:
        """Extract signature information"""
        signatures = []
        
        # Look for signature blocks
        signature_patterns = [
            r'(?:signed by|signature of)[\s:]+([^\n]+)',
            r'(?:authorized signatory)[\s:]+([^\n]+)',
            r'(?:for and on behalf of)[\s:]+([^\n]+)'
        ]
        
        for pattern in signature_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            for match in matches:
                signatures.append({
                    "signer": match.strip(),
                    "type": "digital" if "digital" in match.lower() else "wet"
                })
        
        return signatures
    
    def _extract_witnesses(self, text: str) -> List[str]:
        """Extract witness information"""
        witnesses = []
        
        witness_patterns = [
            r'(?:witness|witnessed by)[\s:]+([^\n]+)',
            r'(?:in the presence of)[\s:]+([^\n]+)'
        ]
        
        for pattern in witness_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            witnesses.extend([m.strip() for m in matches])
        
        return witnesses
    
    def _extract_special_conditions(self, text: str) -> List[str]:
        """Extract special conditions or riders"""
        conditions = []
        
        # Look for special condition markers
        condition_patterns = [
            r'(?:special condition|rider|addendum)[\s:]+([^.\n]+)',
            r'(?:provided that|subject to)[\s:]+([^.\n]+)'
        ]
        
        for pattern in condition_patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            conditions.extend([m.strip() for m in matches])
        
        return conditions
    
    def _calculate_overall_confidence(self, extracted: Dict) -> float:
        """Calculate overall confidence score"""
        confidence_scores = extracted.get("confidence_scores", {})
        
        if not confidence_scores:
            return 0.5
        
        # Weight critical fields
        weights = {
            "contract_id": 0.15,
            "contract_date": 0.15,
            "parties": 0.25,
            "contract_value": 0.15,
            "effective_date": 0.1,
            "expiry_date": 0.1
        }
        
        total_weighted = 0
        total_weight = 0
        
        for field, weight in weights.items():
            if field == "parties" and (extracted.get("parties", {}).get("first_party") or extracted.get("parties", {}).get("second_party")):
                total_weighted += 0.8 * weight
                total_weight += weight
            elif field in confidence_scores:
                total_weighted += confidence_scores[field] * weight
                total_weight += weight
            elif extracted.get(field):
                total_weighted += 0.7 * weight
                total_weight += weight
        
        return total_weighted / total_weight if total_weight > 0 else 0.5
    
    def to_json(self, extracted_data: Dict[str, Any]) -> str:
        """Convert extracted data to JSON string"""
        return json.dumps(extracted_data, indent=2, default=str)
    
    def to_erp_format(self, extracted_data: Dict[str, Any], erp_system: str = "generic") -> Dict[str, Any]:
        """Convert to ERP format"""
        mapping = {
            "generic": {
                "contract_number": "contract_id",
                "agreement_date": "contract_date",
                "start_date": "effective_date",
                "end_date": "expiry_date",
                "party1": "parties.first_party",
                "party2": "parties.second_party",
                "contract_amount": "contract_value"
            }
        }
        
        erp_data = {"type": "contract", "system": erp_system}
        mapping_dict = mapping.get(erp_system.lower(), mapping["generic"])
        
        for erp_field, source_path in mapping_dict.items():
            parts = source_path.split('.')
            value = extracted_data
            for part in parts:
                if isinstance(value, dict):
                    value = value.get(part)
                else:
                    value = None
                    break
            if value:
                erp_data[erp_field] = value
        
        return erp_data