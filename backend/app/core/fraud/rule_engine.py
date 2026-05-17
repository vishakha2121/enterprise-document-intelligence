"""
Rule Engine for Fraud Detection
Business rules for detecting fraudulent patterns
"""

import re
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime, date
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class RuleSeverity(Enum):
    """Rule severity levels"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class FraudRule:
    """Definition of a fraud detection rule"""
    name: str
    description: str
    severity: RuleSeverity
    check_function: Callable
    weight: float = 1.0

class RuleEngine:
    """
    Business rule engine for fraud detection
    Executes configurable rules to detect fraudulent patterns
    """
    
    def __init__(self):
        """Initialize rule engine with default rules"""
        self.rules: List[FraudRule] = []
        self._register_default_rules()
        logger.info(f"Rule Engine initialized with {len(self.rules)} rules")
    
    def _register_default_rules(self):
        """Register default fraud detection rules"""
        
        # Date validation rules
        self.add_rule(FraudRule(
            name="future_date",
            description="Document contains a future date",
            severity=RuleSeverity.HIGH,
            check_function=self._check_future_date,
            weight=0.8
        ))
        
        self.add_rule(FraudRule(
            name="expired_date",
            description="Document date is more than 1 year old",
            severity=RuleSeverity.MEDIUM,
            check_function=self._check_expired_date,
            weight=0.5
        ))
        
        self.add_rule(FraudRule(
            name="weekend_date",
            description="Document date falls on weekend",
            severity=RuleSeverity.LOW,
            check_function=self._check_weekend_date,
            weight=0.2
        ))
        
        # Amount validation rules
        self.add_rule(FraudRule(
            name="zero_amount",
            description="Document has zero or negative amount",
            severity=RuleSeverity.HIGH,
            check_function=self._check_zero_amount,
            weight=0.9
        ))
        
        self.add_rule(FraudRule(
            name="excessive_amount",
            description="Amount exceeds threshold",
            severity=RuleSeverity.MEDIUM,
            check_function=self._check_excessive_amount,
            weight=0.6
        ))
        
        # Pattern detection rules
        self.add_rule(FraudRule(
            name="suspicious_text",
            description="Document contains suspicious keywords",
            severity=RuleSeverity.MEDIUM,
            check_function=self._check_suspicious_text,
            weight=0.5
        ))
        
        self.add_rule(FraudRule(
            name="inconsistent_currency",
            description="Multiple currencies found in document",
            severity=RuleSeverity.MEDIUM,
            check_function=self._check_inconsistent_currency,
            weight=0.4
        ))
        
        self.add_rule(FraudRule(
            name="missing_required_field",
            description="Required field is missing",
            severity=RuleSeverity.HIGH,
            check_function=self._check_missing_required_fields,
            weight=0.7
        ))
        
        self.add_rule(FraudRule(
            name="invalid_email",
            description="Invalid email format detected",
            severity=RuleSeverity.MEDIUM,
            check_function=self._check_invalid_email,
            weight=0.4
        ))
        
        self.add_rule(FraudRule(
            name="invalid_phone",
            description="Invalid phone number format",
            severity=RuleSeverity.LOW,
            check_function=self._check_invalid_phone,
            weight=0.3
        ))
        
        self.add_rule(FraudRule(
            name="gst_validation",
            description="Invalid GST number format",
            severity=RuleSeverity.MEDIUM,
            check_function=self._check_gst_format,
            weight=0.5
        ))
        
        self.add_rule(FraudRule(
            name="pan_validation",
            description="Invalid PAN number format",
            severity=RuleSeverity.MEDIUM,
            check_function=self._check_pan_format,
            weight=0.5
        ))
    
    def add_rule(self, rule: FraudRule):
        """Add a new rule to the engine"""
        self.rules.append(rule)
        logger.debug(f"Rule added: {rule.name}")
    
    def remove_rule(self, rule_name: str) -> bool:
        """Remove a rule by name"""
        for i, rule in enumerate(self.rules):
            if rule.name == rule_name:
                self.rules.pop(i)
                logger.debug(f"Rule removed: {rule_name}")
                return True
        return False
    
    async def check_rules(
        self,
        text: str,
        extracted_data: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Execute all rules against document
        
        Args:
            text: Document text content
            extracted_data: Extracted structured data
        
        Returns:
            List of rule violations
        """
        violations = []
        
        for rule in self.rules:
            try:
                # Execute rule check
                result = rule.check_function(text, extracted_data)
                
                if result:  # Rule violated
                    violation = {
                        "rule_name": rule.name,
                        "description": rule.description,
                        "severity": rule.severity.value,
                        "severity_weight": rule.weight,
                        "message": result if isinstance(result, str) else rule.description,
                        "details": result if isinstance(result, dict) else {}
                    }
                    violations.append(violation)
            
            except Exception as e:
                logger.error(f"Rule {rule.name} execution failed: {str(e)}")
        
        return violations
    
    # Rule implementation functions
    
    def _check_future_date(self, text: str, data: Optional[Dict]) -> Optional[str]:
        """Check if document has future date"""
        dates = self._extract_dates(text)
        today = date.today()
        
        for dt in dates:
            if dt > today:
                return f"Document contains future date: {dt.isoformat()}"
        
        # Also check extracted data
        if data:
            for key, value in data.items():
                if 'date' in key.lower() and isinstance(value, str):
                    try:
                        dt = datetime.fromisoformat(value.replace('Z', '+00:00')).date()
                        if dt > today:
                            return f"Future date in field '{key}': {value}"
                    except:
                        pass
        
        return None
    
    def _check_expired_date(self, text: str, data: Optional[Dict]) -> Optional[str]:
        """Check if document is too old"""
        dates = self._extract_dates(text)
        one_year_ago = date.today() - datetime.timedelta(days=365).date() if hasattr(datetime, 'timedelta') else None
        
        if one_year_ago:
            for dt in dates:
                if dt < one_year_ago:
                    return f"Document date is more than 1 year old: {dt.isoformat()}"
        
        return None
    
    def _check_weekend_date(self, text: str, data: Optional[Dict]) -> Optional[str]:
        """Check if date falls on weekend"""
        dates = self._extract_dates(text)
        
        for dt in dates:
            if dt.weekday() >= 5:  # 5=Saturday, 6=Sunday
                return f"Document date falls on weekend: {dt.isoformat()}"
        
        return None
    
    def _check_zero_amount(self, text: str, data: Optional[Dict]) -> Optional[str]:
        """Check for zero or negative amounts"""
        if not data:
            return None
        
        for key, value in data.items():
            if any(term in key.lower() for term in ['amount', 'total', 'price', 'subtotal']):
                if isinstance(value, (int, float)):
                    if value <= 0:
                        return f"Zero or negative amount in field '{key}': {value}"
                elif isinstance(value, str):
                    try:
                        num = float(re.sub(r'[^\d.-]', '', value))
                        if num <= 0:
                            return f"Zero or negative amount in field '{key}': {value}"
                    except:
                        pass
        
        return None
    
    def _check_excessive_amount(self, text: str, data: Optional[Dict]) -> Optional[str]:
        """Check if amount exceeds reasonable threshold"""
        threshold = 10000000  # 1 crore / 10 million
        
        if not data:
            return None
        
        for key, value in data.items():
            if any(term in key.lower() for term in ['amount', 'total', 'price']):
                if isinstance(value, (int, float)):
                    if value > threshold:
                        return f"Excessive amount detected: {value} (threshold: {threshold})"
        
        return None
    
    def _check_suspicious_text(self, text: str, data: Optional[Dict]) -> Optional[str]:
        """Check for suspicious keywords"""
        suspicious_keywords = [
            'urgent', 'confidential', 'do not share', 'final version',
            'unauthorized', 'modified', 'fake', 'fraud', 'scam',
            'money laundering', 'offshore', 'untraceable', 'anonymous'
        ]
        
        text_lower = text.lower()
        found = [kw for kw in suspicious_keywords if kw in text_lower]
        
        if found:
            return f"Suspicious keywords found: {', '.join(found[:5])}"
        
        return None
    
    def _check_inconsistent_currency(self, text: str, data: Optional[Dict]) -> Optional[str]:
        """Check for multiple currencies in document"""
        currencies = re.findall(r'(?:₹|Rs\.?|INR|\$|USD|€|EUR|£|GBP)', text)
        
        if currencies:
            unique_currencies = set(currencies)
            if len(unique_currencies) > 1:
                return f"Multiple currencies found: {', '.join(unique_currencies)}"
        
        return None
    
    def _check_missing_required_fields(self, text: str, data: Optional[Dict]) -> Optional[str]:
        """Check for missing required fields"""
        required_fields = ['date', 'amount', 'vendor', 'customer']
        
        if not data:
            return None
        
        missing = []
        for field in required_fields:
            found = False
            for key in data.keys():
                if field in key.lower():
                    found = True
                    break
            if not found:
                missing.append(field)
        
        if missing:
            return f"Missing required fields: {', '.join(missing)}"
        
        return None
    
    def _check_invalid_email(self, text: str, data: Optional[Dict]) -> Optional[str]:
        """Validate email format"""
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        emails = re.findall(email_pattern, text)
        
        for email in emails:
            if len(email) > 100 or '..' in email:
                return f"Suspicious email format: {email}"
        
        return None
    
    def _check_invalid_phone(self, text: str, data: Optional[Dict]) -> Optional[str]:
        """Validate phone number format"""
        phone_pattern = r'\b\d{10}\b|\b\d{3}[-.]?\d{3}[-.]?\d{4}\b'
        phones = re.findall(phone_pattern, text)
        
        suspicious_phones = []
        for phone in phones:
            # Check for repeated digits
            if re.match(r'(\d)\1{9}', phone.replace('-', '').replace('.', '')):
                suspicious_phones.append(phone)
        
        if suspicious_phones:
            return f"Suspicious phone numbers: {', '.join(suspicious_phones[:3])}"
        
        return None
    
    def _check_gst_format(self, text: str, data: Optional[Dict]) -> Optional[str]:
        """Validate GST number format (Indian)"""
        gst_pattern = r'\b\d{2}[A-Z]{5}\d{4}[A-Z]{1}\d{1}[Z]{1}[A-Z\d]{1}\b'
        gst_numbers = re.findall(gst_pattern, text.upper())
        
        invalid_gst = []
        for gst in gst_numbers:
            if len(gst) != 15:
                invalid_gst.append(gst)
        
        if invalid_gst:
            return f"Invalid GST numbers: {', '.join(invalid_gst[:3])}"
        
        return None
    
    def _check_pan_format(self, text: str, data: Optional[Dict]) -> Optional[str]:
        """Validate PAN number format (Indian)"""
        pan_pattern = r'\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b'
        pan_numbers = re.findall(pan_pattern, text.upper())
        
        invalid_pan = []
        for pan in pan_numbers:
            if len(pan) != 10:
                invalid_pan.append(pan)
        
        if invalid_pan:
            return f"Invalid PAN numbers: {', '.join(invalid_pan[:3])}"
        
        return None
    
    def _extract_dates(self, text: str) -> List[date]:
        """Extract dates from text"""
        dates = []
        
        # ISO format dates
        iso_pattern = r'\b\d{4}-\d{2}-\d{2}\b'
        for match in re.findall(iso_pattern, text):
            try:
                dates.append(datetime.strptime(match, '%Y-%m-%d').date())
            except:
                pass
        
        # DD/MM/YYYY format
        dmy_pattern = r'\b\d{2}/\d{2}/\d{4}\b'
        for match in re.findall(dmy_pattern, text):
            try:
                dates.append(datetime.strptime(match, '%d/%m/%Y').date())
            except:
                pass
        
        return dates
    
    def get_rules_summary(self) -> Dict[str, Any]:
        """Get summary of all registered rules"""
        return {
            "total_rules": len(self.rules),
            "rules": [
                {
                    "name": rule.name,
                    "severity": rule.severity.value,
                    "weight": rule.weight,
                    "description": rule.description
                }
                for rule in self.rules
            ],
            "severity_breakdown": {
                severity.value: len([r for r in self.rules if r.severity == severity])
                for severity in RuleSeverity
            }
        }