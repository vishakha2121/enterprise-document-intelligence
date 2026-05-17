"""
ERP Integration Service
Auto-fill ERP systems with extracted data
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
import json
import httpx
from enum import Enum

from app.core.extraction.field_mapper import FieldMapper, ERPSystem
from app.config import settings

logger = logging.getLogger(__name__)

class ERPIntegrationService:
    """Service for ERP system integration and auto-fill"""
    
    def __init__(self):
        self.field_mapper = FieldMapper()
        self.erp_configs = self._load_erp_configs()
    
    def _load_erp_configs(self) -> Dict[str, Dict[str, Any]]:
        """Load ERP system configurations"""
        return {
            ERPSystem.SAP.value: {
                "base_url": "https://api.sap.com/v1",
                "endpoints": {
                    "invoice": "/invoice/create",
                    "contract": "/contract/create"
                },
                "auth_type": "oauth2"
            },
            ERPSystem.QUICKBOOKS.value: {
                "base_url": "https://quickbooks.api.intuit.com/v3",
                "endpoints": {
                    "invoice": "/invoice",
                    "customer": "/customer"
                },
                "auth_type": "oauth2"
            },
            ERPSystem.ZOHO.value: {
                "base_url": "https://www.zohoapis.com/books/v3",
                "endpoints": {
                    "invoice": "/invoices",
                    "salesorder": "/salesorders"
                },
                "auth_type": "oauth2"
            },
            ERPSystem.TALLY.value: {
                "base_url": "http://localhost:9000",
                "endpoints": {
                    "voucher": "/tally/import"
                },
                "auth_type": "basic"
            }
        }
    
    async def push_to_erp(
        self,
        extracted_data: Dict[str, Any],
        document_type: str,
        erp_system: str,
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Push extracted data to ERP system
        
        Args:
            extracted_data: Extracted document data
            document_type: Type of document (invoice, contract, form)
            erp_system: Target ERP system
            api_key: API key for authentication
        
        Returns:
            Push result with status and response
        """
        try:
            # Map data to ERP format
            erp_data = await self.field_mapper.map_to_erp(
                extracted_data,
                document_type,
                ERPSystem(erp_system.lower())
            )
            
            # Get ERP configuration
            erp_config = self.erp_configs.get(erp_system.lower())
            if not erp_config:
                return {
                    "success": False,
                    "error": f"ERP system {erp_system} not supported"
                }
            
            # Determine endpoint
            endpoint = erp_config["endpoints"].get(document_type)
            if not endpoint:
                endpoint = erp_config["endpoints"].get("default", "/import")
            
            url = f"{erp_config['base_url']}{endpoint}"
            
            # Prepare headers
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            
            # Make API call
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    json=erp_data,
                    headers=headers
                )
                
                if response.status_code in [200, 201]:
                    return {
                        "success": True,
                        "status_code": response.status_code,
                        "message": f"Data successfully pushed to {erp_system}",
                        "response": response.json() if response.text else {},
                        "erp_data": erp_data
                    }
                else:
                    return {
                        "success": False,
                        "status_code": response.status_code,
                        "error": f"ERP API returned {response.status_code}: {response.text}",
                        "erp_data": erp_data
                    }
        
        except httpx.TimeoutException:
            return {
                "success": False,
                "error": f"Timeout connecting to {erp_system}",
                "erp_data": erp_data if 'erp_data' in locals() else None
            }
        except Exception as e:
            logger.error(f"ERP push failed: {str(e)}")
            return {
                "success": False,
                "error": str(e),
                "erp_data": erp_data if 'erp_data' in locals() else None
            }
    
    async def generate_erp_payload(
        self,
        extracted_data: Dict[str, Any],
        document_type: str,
        erp_system: str,
        include_validation: bool = True
    ) -> Dict[str, Any]:
        """Generate ERP payload without sending"""
        erp_data = await self.field_mapper.map_to_erp(
            extracted_data,
            document_type,
            ERPSystem(erp_system.lower())
        )
        
        if include_validation:
            # Validate required fields
            validation = self._validate_erp_payload(erp_data, document_type, erp_system)
            erp_data["validation"] = validation
        
        return erp_data
    
    def _validate_erp_payload(
        self,
        payload: Dict[str, Any],
        document_type: str,
        erp_system: str
    ) -> Dict[str, Any]:
        """Validate ERP payload for required fields"""
        # Define required fields for each ERP system and document type
        required_fields_map = {
            "invoice": {
                "sap": ["VBELN", "NETWR"],
                "quickbooks": ["InvoiceNumber", "TotalAmount"],
                "zoho": ["invoice_number", "total"],
                "tally": ["BillNo", "BillAmount"]
            },
            "contract": {
                "sap": ["VBELN", "NETWR"],
                "generic": ["contract_number", "contract_value"]
            }
        }
        
        required = required_fields_map.get(document_type, {}).get(erp_system, [])
        missing_fields = [field for field in required if field not in payload.get("fields", {})]
        
        return {
            "valid": len(missing_fields) == 0,
            "missing_fields": missing_fields,
            "total_fields": len(payload.get("fields", {})),
            "warnings": [] if payload.get("warnings") is None else payload["warnings"]
        }
    
    async def get_supported_erp_systems(self) -> List[Dict[str, Any]]:
        """Get list of supported ERP systems"""
        return [
            {
                "name": system.value,
                "display_name": system.value.upper(),
                "supported_document_types": ["invoice", "contract", "form"],
                "requires_auth": True,
                "auth_type": self.erp_configs.get(system.value, {}).get("auth_type", "oauth2")
            }
            for system in ERPSystem
        ]
    
    async def test_connection(
        self,
        erp_system: str,
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Test connection to ERP system"""
        erp_config = self.erp_configs.get(erp_system.lower())
        if not erp_config:
            return {
                "success": False,
                "error": f"ERP system {erp_system} not supported"
            }
        
        try:
            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{erp_config['base_url']}/health",
                    headers=headers
                )
                
                return {
                    "success": response.status_code == 200,
                    "status_code": response.status_code,
                    "message": "Connection successful" if response.status_code == 200 else "Connection failed"
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_erp_field_mapping(
        self,
        erp_system: str,
        document_type: str
    ) -> Dict[str, Any]:
        """Get field mapping for specific ERP system"""
        summary = self.field_mapper.get_mapping_summary(document_type)
        
        if erp_system in summary.get("erp_systems", {}):
            return {
                "erp_system": erp_system,
                "document_type": document_type,
                "mapping": summary["erp_systems"][erp_system]
            }
        
        return {"error": f"No mapping found for {erp_system} and {document_type}"}
    
    async def auto_fill_erp_form(
        self,
        extracted_data: Dict[str, Any],
        document_type: str,
        erp_system: str,
        form_url: str,
        api_key: Optional[str] = None
    ) -> Dict[str, Any]:
        """Auto-fill ERP web form with extracted data"""
        # Generate ERP payload
        payload = await self.generate_erp_payload(extracted_data, document_type, erp_system)
        
        # Submit to form endpoint
        try:
            headers = {
                "Content-Type": "application/x-www-form-urlencoded"
            }
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    form_url,
                    data=payload.get("fields", {}),
                    headers=headers
                )
                
                return {
                    "success": response.status_code in [200, 302, 201],
                    "status_code": response.status_code,
                    "message": "Form auto-filled successfully" if response.status_code in [200, 302] else "Auto-fill failed",
                    "response_url": response.headers.get("Location") if response.status_code == 302 else None
                }
        
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_erp_templates(self, erp_system: str) -> Dict[str, Any]:
        """Get import templates for ERP system"""
        templates = {
            "sap": {
                "invoice": {
                    "format": "IDoc",
                    "required_fields": ["VBELN", "FKDAT", "NETWR", "KUNNR"],
                    "sample": {
                        "VBELN": "INV-2024-001",
                        "FKDAT": "2024-01-15",
                        "NETWR": "1500.00",
                        "KUNNR": "CUST001"
                    }
                }
            },
            "quickbooks": {
                "invoice": {
                    "format": "JSON",
                    "required_fields": ["InvoiceNumber", "InvoiceDate", "TotalAmount", "CustomerName"],
                    "sample": {
                        "InvoiceNumber": "INV-001",
                        "InvoiceDate": "2024-01-15",
                        "TotalAmount": 1500.00,
                        "CustomerName": "ABC Corp"
                    }
                }
            }
        }
        
        return templates.get(erp_system, {})