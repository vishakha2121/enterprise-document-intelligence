"""
Named Entity Recognition (NER) Extractor
Extracts key entities like dates, amounts, names, IDs from documents
"""

import torch
from transformers import AutoTokenizer, AutoModelForTokenClassification
from transformers import pipeline
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
import re
from datetime import datetime
import logging
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time

from app.config import settings
from app.core.nlp.text_cleaner import TextCleaner

logger = logging.getLogger(__name__)

class NERExtractor:
    """
    Named Entity Recognition for document information extraction
    Extracts: dates, amounts, invoice numbers, names, organizations, etc.
    """
    
    # Entity types mapping
    ENTITY_TYPES = {
        "DATE": "date",
        "MONEY": "amount",
        "PERCENT": "percentage",
        "CARDINAL": "number",
        "ORG": "organization",
        "PERSON": "person_name",
        "GPE": "location",
        "PRODUCT": "product",
        "EMAIL": "email",
        "PHONE": "phone",
        "INVOICE_NUM": "invoice_number",
        "CONTRACT_ID": "contract_id",
        "TAX_ID": "tax_id",
        "BANK_ACCOUNT": "bank_account"
    }
    
    # Regex patterns for entity extraction (fallback)
    REGEX_PATTERNS = {
        "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "phone": r'\b(?:\+?91)?[0-9]{10}\b|\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
        "invoice_number": r'\b(?:INV|INVOICE|INV-|INV_|#)?\s?[A-Z0-9]{4,20}\b',
        "contract_id": r'\b(?:CT|CONTRACT|CONT-|CT_|#)?\s?[A-Z0-9]{4,20}\b',
        "tax_id": r'\b(?:GST|PAN|TIN|VAT|TAX|ID)?\s?[A-Z0-9]{5,20}\b',
        "amount_currency": r'\b(?:₹|Rs\.?|INR|\$|USD|€|EUR|£|GBP)\s?\d+(?:[,.]\d{2})?\b',
        "date_iso": r'\b\d{4}-\d{2}-\d{2}\b',
        "date_dmy": r'\b\d{2}/\d{2}/\d{4}\b|\b\d{2}-\d{2}-\d{4}\b',
        "date_mdy": r'\b\d{1,2}/\d{1,2}/\d{4}\b'
    }
    
    def __init__(self):
        """Initialize NER extractor"""
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.text_cleaner = TextCleaner()
        self.ner_pipeline = None
        self.is_loaded = False
        
        # Thread pool for async operations
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        # Load NER model
        self._load_ner_model()
        
        logger.info(f"NER Extractor initialized on {self.device}")
    
    def _load_ner_model(self):
        """Load pre-trained NER model"""
        try:
            model_name = "dslim/bert-base-NER"  # Lightweight NER model
            self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            self.model = AutoModelForTokenClassification.from_pretrained(model_name)
            self.model.to(self.device)
            
            # Create pipeline
            self.ner_pipeline = pipeline(
                "ner",
                model=self.model,
                tokenizer=self.tokenizer,
                device=0 if torch.cuda.is_available() else -1,
                aggregation_strategy="simple"
            )
            
            self.is_loaded = True
            logger.info("NER model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load NER model: {str(e)}")
            self.is_loaded = False
    
    async def extract_entities(
        self,
        text: str,
        entity_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Extract named entities from document text
        
        Args:
            text: Document text
            entity_types: Specific entity types to extract (None for all)
        
        Returns:
            Dictionary with extracted entities
        """
        start_time = time.time()
        
        # Clean text
        cleaned_text = self.text_cleaner.clean_text(text)
        
        if not cleaned_text:
            return {
                "success": False,
                "error": "Empty text",
                "entities": {},
                "entities_list": []
            }
        
        # Extract using BERT NER
        bert_entities = []
        if self.is_loaded:
            bert_entities = await self._extract_with_bert(cleaned_text)
        
        # Extract using regex patterns (always as fallback)
        regex_entities = self._extract_with_regex(cleaned_text)
        
        # Merge entities (prefer BERT results)
        all_entities = self._merge_entities(bert_entities, regex_entities)
        
        # Filter by requested types
        if entity_types:
            all_entities = [
                e for e in all_entities 
                if e["type"] in entity_types
            ]
        
        # Group by entity type
        grouped_entities = {}
        for entity in all_entities:
            e_type = entity["type"]
            if e_type not in grouped_entities:
                grouped_entities[e_type] = []
            grouped_entities[e_type].append(entity)
        
        # Deduplicate and sort by confidence
        for e_type in grouped_entities:
            grouped_entities[e_type] = self._deduplicate_entities(grouped_entities[e_type])
        
        # Extract key fields (specific formats)
        key_fields = self._extract_key_fields(cleaned_text, all_entities)
        
        processing_time = (time.time() - start_time) * 1000
        
        return {
            "success": True,
            "entities": grouped_entities,
            "entities_list": all_entities,
            "key_fields": key_fields,
            "total_entities": len(all_entities),
            "processing_time_ms": processing_time,
            "model_used": "bert_ner" if self.is_loaded else "regex_only"
        }
    
    async def _extract_with_bert(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities using BERT NER model"""
        try:
            # Run NER pipeline
            loop = asyncio.get_event_loop()
            results = await loop.run_in_executor(
                self.executor,
                lambda: self.ner_pipeline(text[:512])  # Limit length for performance
            )
            
            entities = []
            for entity in results:
                # Map BERT entity type to our type
                entity_type = self._map_entity_type(entity["entity_group"])
                
                entities.append({
                    "text": entity["word"],
                    "type": entity_type,
                    "confidence": entity["score"],
                    "start": entity["start"],
                    "end": entity["end"]
                })
            
            return entities
        
        except Exception as e:
            logger.error(f"BERT NER extraction failed: {str(e)}")
            return []
    
    def _extract_with_regex(self, text: str) -> List[Dict[str, Any]]:
        """Extract entities using regex patterns"""
        entities = []
        
        # Extract email addresses
        for match in re.finditer(self.REGEX_PATTERNS["email"], text, re.IGNORECASE):
            entities.append({
                "text": match.group(),
                "type": "email",
                "confidence": 0.85,
                "method": "regex"
            })
        
        # Extract phone numbers
        for match in re.finditer(self.REGEX_PATTERNS["phone"], text):
            entities.append({
                "text": match.group(),
                "type": "phone",
                "confidence": 0.9,
                "method": "regex"
            })
        
        # Extract invoice numbers
        for match in re.finditer(self.REGEX_PATTERNS["invoice_number"], text, re.IGNORECASE):
            entities.append({
                "text": match.group(),
                "type": "invoice_number",
                "confidence": 0.88,
                "method": "regex"
            })
        
        # Extract contract IDs
        for match in re.finditer(self.REGEX_PATTERNS["contract_id"], text, re.IGNORECASE):
            entities.append({
                "text": match.group(),
                "type": "contract_id",
                "confidence": 0.87,
                "method": "regex"
            })
        
        # Extract tax IDs
        for match in re.finditer(self.REGEX_PATTERNS["tax_id"], text, re.IGNORECASE):
            entities.append({
                "text": match.group(),
                "type": "tax_id",
                "confidence": 0.85,
                "method": "regex"
            })
        
        # Extract amounts with currency
        amount_pattern = r'\b(?:₹|Rs\.?|INR|\$|USD|€|EUR|£|GBP)\s?(\d+(?:[,.]\d{2})?)\b'
        for match in re.finditer(amount_pattern, text, re.IGNORECASE):
            entities.append({
                "text": match.group(),
                "type": "amount",
                "confidence": 0.92,
                "value": float(match.group(1).replace(',', '')),
                "method": "regex"
            })
        
        # Extract dates
        date_patterns = [self.REGEX_PATTERNS["date_iso"], self.REGEX_PATTERNS["date_dmy"]]
        for pattern in date_patterns:
            for match in re.finditer(pattern, text):
                entities.append({
                    "text": match.group(),
                    "type": "date",
                    "confidence": 0.9,
                    "method": "regex"
                })
        
        return entities
    
    def _merge_entities(
        self,
        bert_entities: List[Dict[str, Any]],
        regex_entities: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Merge entities from BERT and regex, preferring BERT for overlapping"""
        # Simple merge - add regex entities that don't overlap with BERT
        merged = list(bert_entities)
        
        # For regex entities, check if text already exists in BERT results
        bert_texts = {e["text"].lower() for e in bert_entities}
        
        for regex_entity in regex_entities:
            if regex_entity["text"].lower() not in bert_texts:
                merged.append(regex_entity)
        
        return merged
    
    def _map_entity_type(self, bert_type: str) -> str:
        """Map BERT entity type to our type"""
        mapping = {
            "ORG": "organization",
            "PER": "person_name",
            "LOC": "location",
            "DATE": "date",
            "MONEY": "amount",
            "PERCENT": "percentage",
            "CARDINAL": "number"
        }
        return mapping.get(bert_type, bert_type.lower())
    
    def _deduplicate_entities(self, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate entities and keep highest confidence"""
        unique = {}
        for entity in entities:
            text_lower = entity["text"].lower()
            if text_lower not in unique or entity["confidence"] > unique[text_lower]["confidence"]:
                unique[text_lower] = entity
        
        return sorted(unique.values(), key=lambda x: x["confidence"], reverse=True)
    
    def _extract_key_fields(
        self,
        text: str,
        all_entities: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract specific key fields from document"""
        key_fields = {}
        
        # Find invoice number
        for entity in all_entities:
            if entity["type"] == "invoice_number":
                key_fields["invoice_number"] = entity["text"]
                break
        
        # Find total amount
        for entity in all_entities:
            if entity["type"] == "amount":
                # Try to get numeric value
                amount_str = entity["text"]
                numbers = re.findall(r'\d+(?:[,.]\d+)?', amount_str)
                if numbers:
                    value = float(numbers[0].replace(',', ''))
                    key_fields["total_amount"] = value
                    key_fields["amount_currency"] = re.sub(r'[\d\s,.]', '', amount_str)
                break
        
        # Find dates
        dates = [e["text"] for e in all_entities if e["type"] == "date"]
        if dates:
            key_fields["date"] = dates[0]
        
        # Find organization/vendor
        for entity in all_entities:
            if entity["type"] == "organization":
                key_fields["vendor_name"] = entity["text"]
                break
        
        # Find person/customer
        for entity in all_entities:
            if entity["type"] == "person_name":
                key_fields["customer_name"] = entity["text"]
                break
        
        # Extract using additional patterns
        # GST number
        gst_pattern = r'\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}\d{1}[Z]{1}[A-Z\d]{1}\b'
        gst_match = re.search(gst_pattern, text, re.IGNORECASE)
        if gst_match:
            key_fields["gst_number"] = gst_match.group()
        
        # PAN number
        pan_pattern = r'\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b'
        pan_match = re.search(pan_pattern, text, re.IGNORECASE)
        if pan_match:
            key_fields["pan_number"] = pan_match.group()
        
        return key_fields
    
    async def extract_invoice_fields(self, text: str) -> Dict[str, Any]:
        """Specialized extraction for invoice documents"""
        result = await self.extract_entities(text)
        
        # Extract invoice-specific fields
        invoice_fields = {
            "invoice_number": None,
            "invoice_date": None,
            "due_date": None,
            "vendor_name": None,
            "vendor_gst": None,
            "customer_name": None,
            "customer_gst": None,
            "subtotal": None,
            "tax_amount": None,
            "total_amount": None,
            "currency": None,
            "payment_terms": None
        }
        
        key_fields = result.get("key_fields", {})
        invoice_fields.update(key_fields)
        
        # Extract due date (often after "due date" or "payment due")
        due_date_pattern = r'(?:due date|payment due|pay by)[\s:]+(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
        due_match = re.search(due_date_pattern, text, re.IGNORECASE)
        if due_match:
            invoice_fields["due_date"] = due_match.group(1)
        
        # Extract GST numbers
        gst_numbers = []
        for entity in result.get("entities_list", []):
            if entity["type"] == "tax_id" and "gst" in entity["text"].lower():
                gst_numbers.append(entity["text"])
        
        if gst_numbers:
            invoice_fields["vendor_gst"] = gst_numbers[0]
            if len(gst_numbers) > 1:
                invoice_fields["customer_gst"] = gst_numbers[1]
        
        return invoice_fields
    
    async def extract_contract_fields(self, text: str) -> Dict[str, Any]:
        """Specialized extraction for contract documents"""
        result = await self.extract_entities(text)
        
        contract_fields = {
            "contract_id": None,
            "contract_date": None,
            "effective_date": None,
            "expiry_date": None,
            "parties_involved": [],
            "contract_value": None,
            "currency": None,
            "term_months": None
        }
        
        # Extract contract ID
        for entity in result.get("entities_list", []):
            if entity["type"] == "contract_id":
                contract_fields["contract_id"] = entity["text"]
                break
        
        # Extract parties (organizations and persons)
        for entity in result.get("entities_list", []):
            if entity["type"] == "organization":
                contract_fields["parties_involved"].append(entity["text"])
            elif entity["type"] == "person_name":
                contract_fields["parties_involved"].append(entity["text"])
        
        # Extract contract value
        value_pattern = r'(?:contract value|amount|consideration)[\s:]+(?:₹|Rs\.?|\$)?\s?(\d+(?:[,.]\d+)?)'
        value_match = re.search(value_pattern, text, re.IGNORECASE)
        if value_match:
            contract_fields["contract_value"] = float(value_match.group(1).replace(',', ''))
        
        # Extract term (months/years)
        term_pattern = r'term[\s:]+(\d+)\s*(?:month|year)s?'
        term_match = re.search(term_pattern, text, re.IGNORECASE)
        if term_match:
            months = int(term_match.group(1))
            if 'year' in term_match.group(0).lower():
                months *= 12
            contract_fields["term_months"] = months
        
        contract_fields.update(result.get("key_fields", {}))
        
        return contract_fields
    
    async def extract_form_fields(self, text: str) -> Dict[str, Any]:
        """Specialized extraction for form/documents"""
        result = await self.extract_entities(text)
        
        form_fields = {
            "form_id": None,
            "submission_date": None,
            "applicant_name": None,
            "applicant_details": {},
            "purpose": None,
            "declarations_signed": False
        }
        
        # Extract applicant name (often after "name" or "applicant")
        name_pattern = r'(?:name of applicant|applicant name|full name)[\s:]+([A-Za-z\s]+)'
        name_match = re.search(name_pattern, text, re.IGNORECASE)
        if name_match:
            form_fields["applicant_name"] = name_match.group(1).strip()
        
        # Extract purpose
        purpose_pattern = r'(?:purpose|reason for application)[\s:]+([^\n]+)'
        purpose_match = re.search(purpose_pattern, text, re.IGNORECASE)
        if purpose_match:
            form_fields["purpose"] = purpose_match.group(1).strip()
        
        # Check for signature/declaration
        if re.search(r'(?:signature|declaration|agree|consent)', text, re.IGNORECASE):
            form_fields["declarations_signed"] = True
        
        form_fields.update(result.get("key_fields", {}))
        
        return form_fields
    
    def get_supported_entities(self) -> List[str]:
        """Get list of supported entity types"""
        return list(self.ENTITY_TYPES.values())