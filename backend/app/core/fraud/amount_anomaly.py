"""
Amount Anomaly Detector
Detects anomalies and inconsistencies in monetary amounts
"""

import re
import logging
from typing import Dict, Any, List, Optional, Tuple
from decimal import Decimal, InvalidOperation
import numpy as np
from collections import defaultdict

logger = logging.getLogger(__name__)

class AmountAnomalyDetector:
    """
    Detects anomalies in amounts, totals, and financial calculations
    Checks for mathematical inconsistencies and suspicious patterns
    """
    
    def __init__(self):
        """Initialize amount anomaly detector"""
        # Patterns for amount extraction
        self.amount_patterns = {
            "currency": r'(?:₹|Rs\.?|INR|\$|USD|€|EUR|£|GBP)\s?(\d+(?:[,.]\d+)?)',
            "number": r'\b(\d+(?:[,.]\d+)?)\b',
            "percentage": r'(\d+(?:[,.]\d+)?)\s?%',
            "tax_rate": r'(?:tax|gst|vat)\s*[:]?\s*(\d+(?:[,.]\d+)?)\s?%'
        }
        
        # Suspicious amount patterns
        self.suspicious_patterns = {
            "round_numbers": r'\b\d+000\b',  # Round thousands
            "repeated_digits": r'\b(\d)\1{2,}\b',  # 111, 222, etc.
            "sequential": r'\b12345|23456|34567|45678|56789\b'  # Sequential numbers
        }
        
        logger.info("Amount Anomaly Detector initialized")
    
    async def detect_anomalies(
        self,
        extracted_data: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Detect anomalies in extracted amounts
        
        Args:
            extracted_data: Extracted data containing amounts
        
        Returns:
            List of detected anomalies
        """
        anomalies = []
        
        # Extract all amounts from data
        amounts = self._extract_amounts(extracted_data)
        
        if not amounts:
            return anomalies
        
        # Check subtotal vs total mismatch
        subtotal_anomaly = self._check_subtotal_total_mismatch(extracted_data)
        if subtotal_anomaly:
            anomalies.append(subtotal_anomaly)
        
        # Check tax calculation
        tax_anomaly = self._check_tax_calculation(extracted_data)
        if tax_anomaly:
            anomalies.append(tax_anomaly)
        
        # Check line items sum
        line_items_anomaly = self._check_line_items_sum(extracted_data)
        if line_items_anomaly:
            anomalies.append(line_items_anomaly)
        
        # Check for suspicious amount patterns
        suspicious_patterns = self._check_suspicious_patterns(amounts)
        anomalies.extend(suspicious_patterns)
        
        # Check for statistical anomalies
        stat_anomalies = self._check_statistical_anomalies(amounts)
        anomalies.extend(stat_anomalies)
        
        return anomalies
    
    def _extract_amounts(self, data: Dict[str, Any]) -> List[float]:
        """Extract all numeric amounts from data"""
        amounts = []
        
        def extract_recursive(obj):
            if isinstance(obj, dict):
                for key, value in obj.items():
                    if any(term in key.lower() for term in ['amount', 'total', 'price', 'cost', 'fee', 'tax', 'subtotal']):
                        if isinstance(value, (int, float)):
                            amounts.append(float(value))
                        elif isinstance(value, str):
                            try:
                                # Clean string and convert to float
                                cleaned = re.sub(r'[^\d.-]', '', value)
                                if cleaned:
                                    amounts.append(float(cleaned))
                            except:
                                pass
                    else:
                        extract_recursive(value)
            elif isinstance(obj, list):
                for item in obj:
                    extract_recursive(item)
        
        extract_recursive(data)
        return amounts
    
    def _check_subtotal_total_mismatch(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check if subtotal and total amounts are consistent"""
        subtotal = None
        total = None
        
        # Find subtotal and total in data
        for key, value in data.items():
            if 'subtotal' in key.lower() and isinstance(value, (int, float)):
                subtotal = float(value)
            elif 'total' in key.lower() and isinstance(value, (int, float)):
                total = float(value)
        
        if subtotal is not None and total is not None:
            # Allow for small rounding differences (0.01)
            if abs(total - subtotal) > 0.01 and subtotal != 0:
                difference = total - subtotal
                difference_percent = (difference / subtotal) * 100
                
                return {
                    "type": "subtotal_total_mismatch",
                    "description": f"Total ({total}) does not match subtotal ({subtotal})",
                    "severity": "high" if abs(difference_percent) > 10 else "medium",
                    "confidence": 0.9,
                    "severity_weight": 0.4,
                    "details": {
                        "subtotal": subtotal,
                        "total": total,
                        "difference": difference,
                        "difference_percent": difference_percent
                    }
                }
        
        return None
    
    def _check_tax_calculation(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check if tax calculation is correct"""
        subtotal = None
        tax_amount = None
        tax_rate = None
        total = None
        
        for key, value in data.items():
            if 'subtotal' in key.lower() and isinstance(value, (int, float)):
                subtotal = float(value)
            elif 'tax' in key.lower() and 'amount' in key.lower() and isinstance(value, (int, float)):
                tax_amount = float(value)
            elif 'tax' in key.lower() and 'rate' in key.lower() and isinstance(value, (int, float)):
                tax_rate = float(value)
            elif 'total' in key.lower() and isinstance(value, (int, float)):
                total = float(value)
        
        # Check tax amount vs rate
        if subtotal is not None and tax_rate is not None:
            expected_tax = subtotal * (tax_rate / 100)
            if tax_amount is not None and abs(tax_amount - expected_tax) > 0.01:
                return {
                    "type": "tax_calculation_mismatch",
                    "description": f"Tax amount ({tax_amount}) does not match {tax_rate}% of subtotal ({expected_tax:.2f})",
                    "severity": "high",
                    "confidence": 0.85,
                    "severity_weight": 0.35,
                    "details": {
                        "subtotal": subtotal,
                        "tax_rate": tax_rate,
                        "expected_tax": expected_tax,
                        "actual_tax": tax_amount
                    }
                }
        
        # Check total = subtotal + tax
        if subtotal is not None and tax_amount is not None and total is not None:
            expected_total = subtotal + tax_amount
            if abs(total - expected_total) > 0.01:
                return {
                    "type": "total_calculation_mismatch",
                    "description": f"Total ({total}) does not equal subtotal + tax ({subtotal} + {tax_amount} = {expected_total:.2f})",
                    "severity": "critical",
                    "confidence": 0.95,
                    "severity_weight": 0.5,
                    "details": {
                        "subtotal": subtotal,
                        "tax": tax_amount,
                        "expected_total": expected_total,
                        "actual_total": total
                    }
                }
        
        return None
    
    def _check_line_items_sum(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Check if line items sum matches total"""
        line_items = data.get('line_items', [])
        
        if not line_items:
            return None
        
        # Calculate sum of line items
        line_items_sum = 0.0
        for item in line_items:
            if isinstance(item, dict):
                for key, value in item.items():
                    if 'amount' in key.lower() and isinstance(value, (int, float)):
                        line_items_sum += float(value)
                    elif 'price' in key.lower() and isinstance(value, (int, float)):
                        line_items_sum += float(value)
                    elif 'total' in key.lower() and isinstance(value, (int, float)):
                        line_items_sum += float(value)
        
        # Find total amount
        total = None
        for key, value in data.items():
            if 'total' in key.lower() and isinstance(value, (int, float)):
                total = float(value)
                break
        
        if total is not None and line_items_sum > 0:
            if abs(total - line_items_sum) > 0.01:
                return {
                    "type": "line_items_mismatch",
                    "description": f"Sum of line items ({line_items_sum:.2f}) does not match total ({total:.2f})",
                    "severity": "high",
                    "confidence": 0.9,
                    "severity_weight": 0.4,
                    "details": {
                        "line_items_sum": line_items_sum,
                        "total": total,
                        "difference": total - line_items_sum
                    }
                }
        
        return None
    
    def _check_suspicious_patterns(self, amounts: List[float]) -> List[Dict[str, Any]]:
        """Check for suspicious amount patterns"""
        anomalies = []
        
        for amount in amounts:
            amount_str = str(int(amount)) if amount == int(amount) else str(amount)
            
            # Check round numbers
            if re.search(self.suspicious_patterns["round_numbers"], amount_str):
                anomalies.append({
                    "type": "suspicious_round_number",
                    "description": f"Amount {amount} is a suspicious round number",
                    "severity": "low",
                    "confidence": 0.6,
                    "severity_weight": 0.15,
                    "details": {"amount": amount, "pattern": "round_number"}
                })
            
            # Check repeated digits
            if re.search(self.suspicious_patterns["repeated_digits"], amount_str):
                anomalies.append({
                    "type": "suspicious_repeated_digits",
                    "description": f"Amount {amount} contains repeated digits",
                    "severity": "low",
                    "confidence": 0.55,
                    "severity_weight": 0.1,
                    "details": {"amount": amount, "pattern": "repeated_digits"}
                })
            
            # Check sequential numbers
            if re.search(self.suspicious_patterns["sequential"], amount_str):
                anomalies.append({
                    "type": "suspicious_sequential",
                    "description": f"Amount {amount} contains sequential digits",
                    "severity": "low",
                    "confidence": 0.5,
                    "severity_weight": 0.1,
                    "details": {"amount": amount, "pattern": "sequential"}
                })
        
        return anomalies
    
    def _check_statistical_anomalies(self, amounts: List[float]) -> List[Dict[str, Any]]:
        """Check for statistical anomalies in amount distribution"""
        if len(amounts) < 3:
            return []
        
        anomalies = []
        
        # Convert to numpy array
        arr = np.array(amounts)
        
        # Calculate Z-scores for outlier detection
        mean = np.mean(arr)
        std = np.std(arr)
        
        if std > 0:
            z_scores = np.abs((arr - mean) / std)
            outliers = np.where(z_scores > 2.5)[0]  # 2.5 standard deviations
            
            for idx in outliers:
                anomalies.append({
                    "type": "statistical_outlier",
                    "description": f"Amount {amounts[idx]:.2f} is a statistical outlier (z-score: {z_scores[idx]:.2f})",
                    "severity": "medium",
                    "confidence": 0.7,
                    "severity_weight": 0.25,
                    "details": {
                        "amount": amounts[idx],
                        "z_score": float(z_scores[idx]),
                        "mean": float(mean),
                        "std": float(std)
                    }
                })
        
        return anomalies
    
    async def validate_amount_consistency(
        self,
        extracted_data: Dict[str, Any],
        expected_ranges: Optional[Dict[str, Tuple[float, float]]] = None
    ) -> Dict[str, Any]:
        """
        Validate amounts against expected ranges
        
        Args:
            extracted_data: Extracted data with amounts
            expected_ranges: Dictionary of field names to (min, max) tuples
        
        Returns:
            Validation results
        """
        results = {
            "valid": True,
            "violations": [],
            "warnings": []
        }
        
        if not expected_ranges:
            return results
        
        for field, (min_val, max_val) in expected_ranges.items():
            # Find field in data
            value = None
            for key, val in extracted_data.items():
                if field.lower() in key.lower():
                    if isinstance(val, (int, float)):
                        value = float(val)
                    break
            
            if value is not None:
                if value < min_val:
                    results["valid"] = False
                    results["violations"].append({
                        "field": field,
                        "value": value,
                        "expected_min": min_val,
                        "message": f"{field} ({value}) is below minimum expected ({min_val})"
                    })
                elif value > max_val:
                    results["valid"] = False
                    results["violations"].append({
                        "field": field,
                        "value": value,
                        "expected_max": max_val,
                        "message": f"{field} ({value}) exceeds maximum expected ({max_val})"
                    })
        
        return results