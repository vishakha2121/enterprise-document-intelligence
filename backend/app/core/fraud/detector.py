"""
Fraud Detection Logic
Multi-layered fraud detection system for documents
"""

import hashlib
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import re
import json
from collections import Counter
import numpy as np
from pathlib import Path
import asyncio
from concurrent.futures import ThreadPoolExecutor

from app.core.fraud.rule_engine import RuleEngine
from app.core.fraud.amount_anomaly import AmountAnomalyDetector
from app.core.fraud.signature_validator import SignatureValidator
from app.core.nlp.text_cleaner import TextCleaner
from app.config import settings

logger = logging.getLogger(__name__)

class FraudDetector:
    """
    Comprehensive fraud detection for documents
    Combines rule-based, anomaly detection, and signature validation
    """
    
    def __init__(self):
        """Initialize fraud detector with all detection engines"""
        self.rule_engine = RuleEngine()
        self.amount_anomaly = AmountAnomalyDetector()
        self.signature_validator = SignatureValidator()
        self.text_cleaner = TextCleaner()
        
        # Thread pool for parallel processing
        self.executor = ThreadPoolExecutor(max_workers=4)
        
        # Suspicious keywords patterns
        self.suspicious_patterns = {
            "urgency": r'\b(?:urgent|immediate|asap|quick|fast track|priority)\b',
            "secrecy": r'\b(?:confidential|do not share|private|secret|classified)\b',
            "modification": r'\b(?:modified|edited|altered|changed|revised|updated)\b',
            "amount_manipulation": r'\b(?:revised amount|corrected amount|new total)\b',
            "authorization": r'\b(?:unauthorized|without approval|pending approval)\b'
        }
        
        # Document tampering indicators
        self.tampering_indicators = [
            r'\\x[0-9a-f]{2}',  # Hex encoding
            r'%[0-9a-f]{2}',     # URL encoding
            r'<script',          # Script tags
            r'javascript:',      # JavaScript
            r'data:image',       # Embedded images
            r'{\\rtf',           # RTF formatting
        ]
        
        logger.info("Fraud Detector initialized with all detection engines")
    
    async def detect_fraud(
        self,
        text: str,
        extracted_data: Optional[Dict[str, Any]] = None,
        document_id: Optional[int] = None,
        previous_version_text: Optional[str] = None,
        check_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Comprehensive fraud detection on document
        
        Args:
            text: Document text content
            extracted_data: Previously extracted structured data
            document_id: Document ID for duplicate checking
            previous_version_text: Previous version text for comparison
            check_types: Specific checks to perform
        
        Returns:
            Fraud detection results with risk score and evidence
        """
        if check_types is None:
            check_types = ["rule_based", "anomaly", "duplicate", "keyword", "tampering"]
        
        results = {}
        risk_factors = []
        evidence_list = []
        total_risk_score = 0.0
        
        # Clean text for analysis
        cleaned_text = self.text_cleaner.clean_text(text, lowercase=True)
        
        # Run selected checks in parallel
        tasks = []
        
        if "rule_based" in check_types:
            tasks.append(self._check_rules(cleaned_text, extracted_data))
        
        if "anomaly" in check_types and extracted_data:
            tasks.append(self._check_anomalies(extracted_data))
        
        if "duplicate" in check_types and document_id:
            tasks.append(self._check_duplicates(document_id, cleaned_text))
        
        if "keyword" in check_types:
            tasks.append(self._check_suspicious_keywords(cleaned_text))
        
        if "tampering" in check_types:
            tasks.append(self._check_tampering(text))
        
        if previous_version_text:
            tasks.append(self._check_version_changes(cleaned_text, previous_version_text))
        
        # Execute all checks in parallel
        check_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for result in check_results:
            if isinstance(result, Exception):
                logger.error(f"Fraud check failed: {str(result)}")
                continue
            
            if result.get("risk_score", 0) > 0:
                risk_factors.append(result)
                evidence_list.extend(result.get("evidence", []))
                total_risk_score += result["risk_score"]
        
        # Calculate overall risk score (0-1)
        overall_risk = min(total_risk_score / len([r for r in check_results if not isinstance(r, Exception)]), 1.0)
        
        # Determine risk level
        if overall_risk >= 0.8:
            risk_level = "critical"
        elif overall_risk >= 0.6:
            risk_level = "high"
        elif overall_risk >= 0.3:
            risk_level = "medium"
        else:
            risk_level = "low"
        
        # Determine if fraudulent
        is_fraudulent = overall_risk >= settings.ANOMALY_THRESHOLD / 4  # Normalize threshold
        
        # Get fraud type
        fraud_type = self._determine_fraud_type(risk_factors)
        
        return {
            "success": True,
            "is_fraudulent": is_fraudulent,
            "risk_score": overall_risk,
            "risk_level": risk_level,
            "fraud_type": fraud_type,
            "evidence": evidence_list[:20],  # Limit evidence
            "risk_factors": risk_factors,
            "checks_performed": check_types,
            "detection_methods": [r.get("method") for r in risk_factors if r.get("method")]
        }
    
    async def _check_rules(
        self,
        text: str,
        extracted_data: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Check business rules for violations"""
        rule_violations = await self.rule_engine.check_rules(text, extracted_data)
        
        if not rule_violations:
            return {"risk_score": 0, "evidence": [], "method": "rule_based"}
        
        # Calculate risk based on rule violations
        risk_score = min(len(rule_violations) * 0.15, 0.8)
        
        evidence = [
            {
                "type": "rule_violation",
                "description": v.get("message", "Rule violation detected"),
                "severity": v.get("severity", "medium"),
                "rule_name": v.get("rule_name"),
                "confidence": 0.85
            }
            for v in rule_violations
        ]
        
        return {
            "risk_score": risk_score,
            "evidence": evidence,
            "method": "rule_based",
            "violations": rule_violations
        }
    
    async def _check_anomalies(self, extracted_data: Dict[str, Any]) -> Dict[str, Any]:
        """Check for anomalies in extracted data"""
        anomalies = await self.amount_anomaly.detect_anomalies(extracted_data)
        
        if not anomalies:
            return {"risk_score": 0, "evidence": [], "method": "anomaly"}
        
        # Calculate risk based on anomalies
        risk_score = min(sum(a.get("severity_weight", 0.2) for a in anomalies), 0.9)
        
        evidence = [
            {
                "type": "amount_anomaly",
                "description": a.get("description", "Amount anomaly detected"),
                "severity": a.get("severity", "medium"),
                "confidence": a.get("confidence", 0.8),
                "details": a.get("details", {})
            }
            for a in anomalies
        ]
        
        return {
            "risk_score": risk_score,
            "evidence": evidence,
            "method": "anomaly",
            "anomalies": anomalies
        }
    
    async def _check_duplicates(
        self,
        document_id: int,
        text: str
    ) -> Dict[str, Any]:
        """Check for duplicate documents"""
        # Calculate document hash
        doc_hash = hashlib.sha256(text.encode()).hexdigest()
        
        # In production, this would query database for existing documents
        # For now, return no duplicate found
        duplicate_found = False
        duplicate_score = 0.0
        
        # Check for exact duplicates (simplified)
        # This would compare with database in production
        
        if duplicate_found:
            return {
                "risk_score": 0.4,
                "evidence": [
                    {
                        "type": "duplicate_document",
                        "description": "Document appears to be duplicate of previously submitted document",
                        "severity": "medium",
                        "confidence": 0.9
                    }
                ],
                "method": "duplicate"
            }
        
        return {"risk_score": 0, "evidence": [], "method": "duplicate"}
    
    async def _check_suspicious_keywords(self, text: str) -> Dict[str, Any]:
        """Check for suspicious keywords and patterns"""
        suspicious_matches = []
        
        for pattern_name, pattern in self.suspicious_patterns.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                suspicious_matches.extend(matches)
        
        if not suspicious_matches:
            return {"risk_score": 0, "evidence": [], "method": "keyword"}
        
        # Calculate risk based on number of matches
        risk_score = min(len(suspicious_matches) * 0.1, 0.6)
        
        evidence = [
            {
                "type": "suspicious_keyword",
                "description": f"Suspicious keyword detected: {', '.join(suspicious_matches[:5])}",
                "severity": "low",
                "confidence": 0.7,
                "matches": suspicious_matches[:10]
            }
        ]
        
        return {
            "risk_score": risk_score,
            "evidence": evidence,
            "method": "keyword",
            "matches": suspicious_matches
        }
    
    async def _check_tampering(self, text: str) -> Dict[str, Any]:
        """Check for document tampering indicators"""
        tampering_found = []
        
        for indicator in self.tampering_indicators:
            if re.search(indicator, text, re.IGNORECASE):
                tampering_found.append(indicator)
        
        if not tampering_found:
            return {"risk_score": 0, "evidence": [], "method": "tampering"}
        
        risk_score = min(len(tampering_found) * 0.25, 1.0)
        
        evidence = [
            {
                "type": "tampering_indicator",
                "description": "Document contains potential tampering indicators",
                "severity": "high",
                "confidence": 0.85,
                "indicators": tampering_found
            }
        ]
        
        return {
            "risk_score": risk_score,
            "evidence": evidence,
            "method": "tampering",
            "indicators": tampering_found
        }
    
    async def _check_version_changes(
        self,
        current_text: str,
        previous_text: str
    ) -> Dict[str, Any]:
        """Check for suspicious changes between document versions"""
        # Calculate similarity
        current_words = set(current_text.split())
        previous_words = set(previous_text.split())
        
        # Added and removed words
        added_words = current_words - previous_words
        removed_words = previous_words - current_words
        
        # Calculate change ratio
        total_unique = len(current_words | previous_words)
        change_ratio = len(added_words | removed_words) / total_unique if total_unique > 0 else 0
        
        # Check for significant changes
        if change_ratio < 0.3:
            return {"risk_score": 0, "evidence": [], "method": "version_check"}
        
        # Calculate risk based on change ratio
        risk_score = min(change_ratio * 0.5, 0.7)
        
        evidence = [
            {
                "type": "significant_changes",
                "description": f"Document has {len(added_words)} new words and {len(removed_words)} removed words",
                "severity": "medium",
                "confidence": 0.75,
                "change_ratio": change_ratio
            }
        ]
        
        return {
            "risk_score": risk_score,
            "evidence": evidence,
            "method": "version_check",
            "change_ratio": change_ratio
        }
    
    def _determine_fraud_type(self, risk_factors: List[Dict[str, Any]]) -> Optional[str]:
        """Determine the type of fraud based on risk factors"""
        fraud_types = []
        
        for factor in risk_factors:
            method = factor.get("method")
            if method == "anomaly":
                fraud_types.append("amount_mismatch")
            elif method == "tampering":
                fraud_types.append("document_tampering")
            elif method == "duplicate":
                fraud_types.append("duplicate_submission")
            elif method == "rule_based":
                violations = factor.get("violations", [])
                for v in violations:
                    if "signature" in v.get("rule_name", "").lower():
                        fraud_types.append("missing_signature")
                    elif "date" in v.get("rule_name", "").lower():
                        fraud_types.append("invalid_date")
                    elif "amount" in v.get("rule_name", "").lower():
                        fraud_types.append("amount_mismatch")
        
        # Return most severe fraud type
        severity_order = ["document_tampering", "amount_mismatch", "duplicate_submission", "missing_signature", "invalid_date"]
        
        for fraud_type in severity_order:
            if fraud_type in fraud_types:
                return fraud_type
        
        return None
    
    async def generate_fraud_report(
        self,
        detection_result: Dict[str, Any],
        document_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Generate detailed fraud analysis report"""
        report = {
            "report_id": hashlib.md5(f"{datetime.now().isoformat()}".encode()).hexdigest()[:8],
            "generated_at": datetime.now().isoformat(),
            "document_id": document_info.get("id"),
            "document_name": document_info.get("filename"),
            "risk_assessment": {
                "risk_score": detection_result["risk_score"],
                "risk_level": detection_result["risk_level"],
                "is_fraudulent": detection_result["is_fraudulent"],
                "fraud_type": detection_result.get("fraud_type")
            },
            "evidence_summary": {
                "total_evidence_items": len(detection_result.get("evidence", [])),
                "by_severity": self._count_by_severity(detection_result.get("evidence", [])),
                "by_type": self._count_by_type(detection_result.get("evidence", []))
            },
            "detailed_findings": detection_result.get("evidence", [])[:10],
            "recommendations": self._generate_recommendations(detection_result),
            "investigation_required": detection_result["risk_score"] > 0.6
        }
        
        return report
    
    def _count_by_severity(self, evidence: List[Dict]) -> Dict[str, int]:
        """Count evidence by severity"""
        counts = {"low": 0, "medium": 0, "high": 0, "critical": 0}
        for e in evidence:
            severity = e.get("severity", "low")
            counts[severity] = counts.get(severity, 0) + 1
        return counts
    
    def _count_by_type(self, evidence: List[Dict]) -> Dict[str, int]:
        """Count evidence by type"""
        counts = {}
        for e in evidence:
            e_type = e.get("type", "unknown")
            counts[e_type] = counts.get(e_type, 0) + 1
        return counts
    
    def _generate_recommendations(self, detection_result: Dict[str, Any]) -> List[str]:
        """Generate recommendations based on detection results"""
        recommendations = []
        
        if detection_result["risk_score"] > 0.8:
            recommendations.append("⚠️ CRITICAL: Flag document for immediate review by fraud investigation team")
            recommendations.append("Do not process this document automatically")
            recommendations.append("Contact the sender to verify document authenticity")
        
        elif detection_result["risk_score"] > 0.5:
            recommendations.append("⚠️ HIGH RISK: Document requires manual review before processing")
            recommendations.append("Verify all extracted information with the sender")
            recommendations.append("Check for document tampering indicators")
        
        elif detection_result["risk_score"] > 0.2:
            recommendations.append("MEDIUM RISK: Review suspicious elements before approval")
            recommendations.append("Validate key fields manually")
        
        # Specific recommendations based on fraud type
        fraud_type = detection_result.get("fraud_type")
        if fraud_type == "amount_mismatch":
            recommendations.append("Verify calculated amounts against line items")
            recommendations.append("Check for mathematical inconsistencies")
        elif fraud_type == "document_tampering":
            recommendations.append("Request original document for comparison")
            recommendations.append("Check document metadata for modification history")
        elif fraud_type == "missing_signature":
            recommendations.append("Request signed version of the document")
        
        return recommendations
    
    def get_detection_stats(self) -> Dict[str, Any]:
        """Get fraud detection statistics"""
        return {
            "detection_methods": ["rule_based", "anomaly", "duplicate", "keyword", "tampering", "version_check"],
            "risk_levels": ["low", "medium", "high", "critical"],
            "fraud_types": ["amount_mismatch", "document_tampering", "duplicate_submission", "missing_signature", "invalid_date"],
            "confidence_threshold": settings.ANOMALY_THRESHOLD
        }