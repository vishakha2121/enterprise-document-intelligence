"""
Fraud Detection Module
Comprehensive fraud detection for documents using multiple strategies
"""

from app.core.fraud.detector import FraudDetector
from app.core.fraud.rule_engine import RuleEngine
from app.core.fraud.amount_anomaly import AmountAnomalyDetector
from app.core.fraud.signature_validator import SignatureValidator

__all__ = [
    "FraudDetector",
    "RuleEngine",
    "AmountAnomalyDetector",
    "SignatureValidator"
]