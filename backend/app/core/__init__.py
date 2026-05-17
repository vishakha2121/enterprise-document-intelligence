"""
Core AI/ML Module
Contains OCR, NLP, Fraud Detection, and Extraction logic
"""

from app.core.ocr.ocr_factory import OCRFactory
from app.core.ocr.tesseract_engine import TesseractEngine
from app.core.ocr.gemini_engine import GeminiEngine
from app.core.ocr.image_preprocessor import ImagePreprocessor

from app.core.nlp.bert_classifier import BERTClassifier
from app.core.nlp.ner_extractor import NERExtractor
from app.core.nlp.text_cleaner import TextCleaner
from app.core.nlp.model_loader import ModelLoader

from app.core.fraud.detector import FraudDetector
from app.core.fraud.rule_engine import RuleEngine
from app.core.fraud.amount_anomaly import AmountAnomalyDetector
from app.core.fraud.signature_validator import SignatureValidator

from app.core.extraction.invoice_extractor import InvoiceExtractor
from app.core.extraction.contract_extractor import ContractExtractor
from app.core.extraction.form_extractor import FormExtractor
from app.core.extraction.field_mapper import FieldMapper

__all__ = [
    # OCR
    "OCRFactory",
    "TesseractEngine",
    "GeminiEngine",
    "ImagePreprocessor",
    # NLP
    "BERTClassifier",
    "NERExtractor",
    "TextCleaner",
    "ModelLoader",
    # Fraud
    "FraudDetector",
    "RuleEngine",
    "AmountAnomalyDetector",
    "SignatureValidator",
    # Extraction
    "InvoiceExtractor",
    "ContractExtractor",
    "FormExtractor",
    "FieldMapper"
]