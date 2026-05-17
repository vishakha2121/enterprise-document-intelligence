"""
Field Mapper for ERP Systems
Maps extracted fields to ERP system-specific fields
"""

import logging
from typing import Dict, Any, List, Optional, Callable
from enum import Enum

logger = logging.getLogger(__name__)

class ERPSystem(Enum):
    """Supported ERP systems"""
    GENERIC = "generic"
    SAP = "sap"
    ORACLE = "oracle"
    QUICKBOOKS = "quickbooks"
    ZOHO = "zoho"
    DYNAMICS = "dynamics"
    TALLY = "tally"
    BUSY = "busy"

class FieldMapper:
    """
    Maps extracted document fields to various ERP system formats
    Supports transformation and validation rules
    """
    
    def __init__(self):
        """Initialize field mapper with mapping rules"""
        self.mappings = self._initialize_mappings()
        self.transformers = self._initialize_transformers()
        self.validators = self._initialize_validators()
        
        logger.info("Field Mapper initialized")
    
    def _initialize_mappings(self) -> Dict[str, Dict[str, Dict[str, str]]]:
        """Initialize field mappings for different document types and ERP systems"""
        return {
            "invoice": {
                ERPSystem.GENERIC.value: {
                    "document_number": "invoice_number",
                    "document_date": "invoice_date",
                    "due_date": "due_date",
                    "vendor_name": "vendor_name",
                    "vendor_gst": "vendor_gst",
                    "customer_name": "customer_name",
                    "customer_gst": "customer_gst",
                    "subtotal": "subtotal",
                    "tax_amount": "tax_amount",
                    "tax_rate": "tax_rate",
                    "total_amount": "total_amount",
                    "currency": "currency",
                    "po_number": "po_number",
                    "payment_terms": "payment_terms"
                },
                ERPSystem.SAP.value: {
                    "VBELN": "invoice_number",
                    "FKDAT": "invoice_date",
                    "NETWR": "total_amount",
                    "KUNNR": "customer_name",
                    "VBRK-WAERK": "currency",
                    "VBELN_VF": "invoice_number"
                },
                ERPSystem.QUICKBOOKS.value: {
                    "InvoiceNumber": "invoice_number",
                    "InvoiceDate": "invoice_date",
                    "DueDate": "due_date",
                    "CustomerName": "customer_name",
                    "CustomerGST": "customer_gst",
                    "Subtotal": "subtotal",
                    "TaxAmount": "tax_amount",
                    "TotalAmount": "total_amount",
                    "Currency": "currency"
                },
                ERPSystem.ZOHO.value: {
                    "invoice_number": "invoice_number",
                    "date": "invoice_date",
                    "due_date": "due_date",
                    "customer_name": "customer_name",
                    "customer_gst": "customer_gst",
                    "sub_total": "subtotal",
                    "tax_total": "tax_amount",
                    "total": "total_amount",
                    "currency_code": "currency"
                },
                ERPSystem.TALLY.value: {
                    "BillNo": "invoice_number",
                    "Date": "invoice_date",
                    "PartyName": "customer_name",
                    "PartyGST": "customer_gst",
                    "BillAmount": "total_amount",
                    "Currency": "currency"
                }
            },
            "contract": {
                ERPSystem.GENERIC.value: {
                    "contract_number": "contract_id",
                    "agreement_date": "contract_date",
                    "effective_date": "effective_date",
                    "expiry_date": "expiry_date",
                    "party1": "parties.first_party",
                    "party2": "parties.second_party",
                    "contract_value": "contract_value",
                    "currency": "currency",
                    "term_months": "term_months"
                },
                ERPSystem.SAP.value: {
                    "VBELN": "contract_id",
                    "BSTKD": "contract_number",
                    "NETWR": "contract_value",
                    "KUNNR": "parties.second_party"
                }
            },
            "form": {
                ERPSystem.GENERIC.value: {
                    "form_id": "form_id",
                    "submission_date": "submission_date",
                    "applicant_name": "applicant_info.name",
                    "applicant_email": "applicant_info.email",
                    "applicant_phone": "applicant_info.phone",
                    "applicant_address": "applicant_info.address"
                }
            }
        }
    
    def _initialize_transformers(self) -> Dict[str, Callable]:
        """Initialize value transformers for different field types"""
        return {
            "date": lambda x: self._format_date(x),
            "amount": lambda x: self._format_amount(x),
            "currency": lambda x: self._normalize_currency(x),
            "gst": lambda x: self._normalize_gst(x),
            "phone": lambda x: self._normalize_phone(x),
            "email": lambda x: x.lower().strip()
        }
    
    def _initialize_validators(self) -> Dict[str, Callable]:
        """Initialize field validators"""
        return {
            "gst": lambda x: bool(re.match(r'^\d{2}[A-Z]{5}\d{4}[A-Z]{1}\d{1}[Z]{1}[A-Z\d]{1}$', x.upper())) if x else True,
            "email": lambda x: bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', x)) if x else True,
            "phone": lambda x: bool(re.match(r'^\+?\d[\d\s-]{8,}\d$', x)) if x else True,
            "pan": lambda x: bool(re.match(r'^[A-Z]{5}[0-9]{4}[A-Z]{1}$', x.upper())) if x else True
        }
    
    async def map_to_erp(
        self,
        extracted_data: Dict[str, Any],
        document_type: str,
        erp_system: ERPSystem = ERPSystem.GENERIC,
        apply_transformations: bool = True,
        validate: bool = True
    ) -> Dict[str, Any]:
        """
        Map extracted data to ERP system format
        
        Args:
            extracted_data: Extracted document data
            document_type: Type of document (invoice, contract, form)
            erp_system: Target ERP system
            apply_transformations: Apply value transformations
            validate: Validate field values
        
        Returns:
            ERP-formatted data
        """
        # Get mapping for document type and ERP system
        doc_mappings = self.mappings.get(document_type, {})
        mapping = doc_mappings.get(erp_system.value, doc_mappings.get(ERPSystem.GENERIC.value, {}))
        
        if not mapping:
            logger.warning(f"No mapping found for {document_type} to {erp_system.value}")
            return {"error": "No mapping available", "original_data": extracted_data}
        
        # Apply mapping
        erp_data = {
            "document_type": document_type,
            "erp_system": erp_system.value,
            "mapped_at": datetime.now().isoformat(),
            "fields": {}
        }
        
        errors = []
        warnings = []
        
        for erp_field, source_path in mapping.items():
            # Get value from extracted data using path
            value = self._get_nested_value(extracted_data, source_path)
            
            if value is not None:
                # Apply transformation
                if apply_transformations:
                    value = self._apply_transformations(value, source_path)
                
                # Validate
                if validate:
                    is_valid, error = self._validate_field(source_path, value)
                    if not is_valid:
                        errors.append({"field": erp_field, "error": error})
                        continue
                
                erp_data["fields"][erp_field] = value
            else:
                warnings.append({"field": erp_field, "warning": f"Source field '{source_path}' not found"})
        
        # Add line items if present
        if "line_items" in extracted_data and extracted_data["line_items"]:
            erp_data["line_items"] = self._map_line_items(
                extracted_data["line_items"],
                document_type,
                erp_system
            )
        
        # Add metadata
        erp_data["metadata"] = {
            "mapping_version": "1.0",
            "transformations_applied": apply_transformations,
            "validation_performed": validate,
            "error_count": len(errors),
            "warning_count": len(warnings)
        }
        
        if errors:
            erp_data["errors"] = errors
        if warnings:
            erp_data["warnings"] = warnings
        
        return erp_data
    
    def _get_nested_value(self, data: Dict, path: str) -> Any:
        """Get nested value using dot notation path"""
        parts = path.split('.')
        current = data
        
        for part in parts:
            if isinstance(current, dict):
                current = current.get(part)
            else:
                return None
        
        return current
    
    def _apply_transformations(self, value: Any, field_path: str) -> Any:
        """Apply transformations based on field type"""
        # Detect field type from path
        field_type = None
        if 'date' in field_path.lower():
            field_type = "date"
        elif any(term in field_path.lower() for term in ['amount', 'total', 'subtotal', 'value']):
            field_type = "amount"
        elif 'currency' in field_path.lower():
            field_type = "currency"
        elif 'gst' in field_path.lower():
            field_type = "gst"
        elif 'phone' in field_path.lower():
            field_type = "phone"
        elif 'email' in field_path.lower():
            field_type = "email"
        
        if field_type and field_type in self.transformers:
            try:
                return self.transformers[field_type](value)
            except Exception as e:
                logger.warning(f"Transformation failed for {field_path}: {str(e)}")
        
        return value
    
    def _validate_field(self, field_path: str, value: Any) -> tuple:
        """Validate field value"""
        # Detect field type
        field_type = None
        if 'gst' in field_path.lower():
            field_type = "gst"
        elif 'email' in field_path.lower():
            field_type = "email"
        elif 'phone' in field_path.lower():
            field_type = "phone"
        elif 'pan' in field_path.lower():
            field_type = "pan"
        
        if field_type and field_type in self.validators:
            try:
                is_valid = self.validators[field_type](value)
                return is_valid, None if is_valid else f"Invalid {field_type} format"
            except Exception as e:
                return False, str(e)
        
        return True, None
    
    def _map_line_items(
        self,
        line_items: List[Dict],
        document_type: str,
        erp_system: ERPSystem
    ) -> List[Dict]:
        """Map line items to ERP format"""
        mapped_items = []
        
        for item in line_items:
            mapped_item = {}
            
            if erp_system == ERPSystem.SAP:
                mapped_item = {
                    "POSNR": item.get("serial_no", ""),
                    "ARKTX": item.get("description", ""),
                    "KWMENG": item.get("quantity", 0),
                    "NETPR": item.get("unit_price", 0),
                    "NETWR": item.get("amount", 0)
                }
            elif erp_system == ERPSystem.QUICKBOOKS:
                mapped_item = {
                    "ItemDesc": item.get("description", ""),
                    "Quantity": item.get("quantity", 0),
                    "Rate": item.get("unit_price", 0),
                    "Amount": item.get("amount", 0)
                }
            else:
                mapped_item = {
                    "serial_no": item.get("serial_no", ""),
                    "description": item.get("description", ""),
                    "quantity": item.get("quantity", 0),
                    "unit_price": item.get("unit_price", 0),
                    "amount": item.get("amount", 0)
                }
            
            mapped_items.append(mapped_item)
        
        return mapped_items
    
    def _format_date(self, value: Any) -> str:
        """Format date to ISO format"""
        if isinstance(value, datetime):
            return value.date().isoformat()
        elif isinstance(value, str):
            # Try to parse various date formats
            for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y', '%d-%m-%Y']:
                try:
                    dt = datetime.strptime(value, fmt)
                    return dt.date().isoformat()
                except:
                    continue
        return str(value)
    
    def _format_amount(self, value: Any) -> float:
        """Format amount to float"""
        if isinstance(value, (int, float)):
            return round(float(value), 2)
        elif isinstance(value, str):
            # Remove currency symbols and commas
            cleaned = re.sub(r'[^\d.-]', '', value)
            try:
                return round(float(cleaned), 2)
            except:
                return 0.0
        return 0.0
    
    def _normalize_currency(self, value: Any) -> str:
        """Normalize currency code"""
        currency_map = {
            '₹': 'INR', 'Rs': 'INR', 'INR': 'INR',
            '$': 'USD', 'USD': 'USD',
            '€': 'EUR', 'EUR': 'EUR',
            '£': 'GBP', 'GBP': 'GBP'
        }
        
        if isinstance(value, str):
            for symbol, code in currency_map.items():
                if symbol in value:
                    return code
        return str(value).upper()
    
    def _normalize_gst(self, value: Any) -> str:
        """Normalize GST number"""
        if isinstance(value, str):
            # Remove spaces and convert to uppercase
            cleaned = re.sub(r'\s', '', value.upper())
            return cleaned
        return str(value)
    
    def _normalize_phone(self, value: Any) -> str:
        """Normalize phone number"""
        if isinstance(value, str):
            # Remove non-digits
            cleaned = re.sub(r'\D', '', value)
            return cleaned
        return str(value)
    
    def get_supported_erp_systems(self) -> List[str]:
        """Get list of supported ERP systems"""
        return [system.value for system in ERPSystem]
    
    def get_supported_document_types(self) -> List[str]:
        """Get list of supported document types"""
        return list(self.mappings.keys())
    
    def get_mapping_summary(self, document_type: str) -> Dict[str, Any]:
        """Get mapping summary for a document type"""
        if document_type not in self.mappings:
            return {"error": f"Document type '{document_type}' not supported"}
        
        summary = {
            "document_type": document_type,
            "erp_systems": {}
        }
        
        for erp_system, mapping in self.mappings[document_type].items():
            summary["erp_systems"][erp_system] = {
                "field_count": len(mapping),
                "fields": list(mapping.keys())
            }
        
        return summary
    
    def add_custom_mapping(
        self,
        document_type: str,
        erp_system: str,
        mapping: Dict[str, str]
    ):
        """Add custom field mapping"""
        if document_type not in self.mappings:
            self.mappings[document_type] = {}
        
        self.mappings[document_type][erp_system] = mapping
        logger.info(f"Custom mapping added for {document_type} to {erp_system}")
    
    def export_mappings(self) -> Dict[str, Any]:
        """Export all mappings as JSON"""
        return self.mappings

# Import datetime for date handling
from datetime import datetime
import re