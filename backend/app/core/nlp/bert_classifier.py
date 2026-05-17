"""
BERT Document Classifier
Classifies documents into types (invoice, contract, form, etc.) using BERT
"""

import torch
import torch.nn as nn
from transformers import BertTokenizer, BertForSequenceClassification, AdamW
from transformers import get_linear_schedule_with_warmup
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
import logging
from pathlib import Path
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
import time

from app.config import settings
from app.core.nlp.text_cleaner import TextCleaner

logger = logging.getLogger(__name__)

class BERTClassifier:
    """
    Document classifier using BERT (Bidirectional Encoder Representations from Transformers)
    Supports multiple document types with confidence scoring
    """
    
    # Document types mapping
    DOCUMENT_TYPES = {
        0: "invoice",
        1: "contract", 
        2: "form",
        3: "receipt",
        4: "report",
        5: "other"
    }
    
    TYPE_TO_ID = {v: k for k, v in DOCUMENT_TYPES.items()}
    
    def __init__(self, model_path: Optional[str] = None):
        """
        Initialize BERT classifier
        
        Args:
            model_path: Path to pre-trained model (None for default)
        """
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model_name = settings.BERT_MODEL_NAME
        self.max_length = settings.MAX_SEQUENCE_LENGTH
        self.confidence_threshold = settings.CLASSIFICATION_THRESHOLD
        self.text_cleaner = TextCleaner()
        
        # Thread pool for async operations
        self.executor = ThreadPoolExecutor(max_workers=2)
        
        # Load model and tokenizer
        self.tokenizer = None
        self.model = None
        self.is_loaded = False
        
        # Try to load model
        if model_path and Path(model_path).exists():
            self._load_model_from_path(model_path)
        else:
            self._load_pretrained_model()
        
        logger.info(f"BERT Classifier initialized on {self.device}")
    
    def _load_pretrained_model(self):
        """Load pre-trained BERT model"""
        try:
            self.tokenizer = BertTokenizer.from_pretrained(self.model_name)
            self.model = BertForSequenceClassification.from_pretrained(
                self.model_name,
                num_labels=len(self.DOCUMENT_TYPES),
                output_attentions=False,
                output_hidden_states=False
            )
            self.model.to(self.device)
            self.model.eval()
            self.is_loaded = True
            logger.info(f"Pre-trained BERT model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load pre-trained BERT: {str(e)}")
            self._create_fallback_classifier()
    
    def _load_model_from_path(self, model_path: str):
        """Load fine-tuned model from path"""
        try:
            self.tokenizer = BertTokenizer.from_pretrained(model_path)
            self.model = BertForSequenceClassification.from_pretrained(model_path)
            self.model.to(self.device)
            self.model.eval()
            self.is_loaded = True
            logger.info(f"Fine-tuned BERT model loaded from {model_path}")
        except Exception as e:
            logger.error(f"Failed to load model from {model_path}: {str(e)}")
            self._load_pretrained_model()
    
    def _create_fallback_classifier(self):
        """Create rule-based fallback classifier"""
        logger.warning("Using rule-based fallback classifier")
        self.is_loaded = False
        
        # Simple keyword-based classification
        self.keyword_map = {
            "invoice": ["invoice", "bill", "payment due", "amount due", "purchase order"],
            "contract": ["contract", "agreement", "terms", "conditions", "parties", "hereby"],
            "form": ["form", "application", "registration", "please complete", "fill out"],
            "receipt": ["receipt", "payment received", "thank you for your payment"],
            "report": ["report", "analysis", "summary", "findings", "conclusion"]
        }
    
    async def classify(
        self,
        text: str,
        return_top_k: int = 3,
        threshold: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        Classify document type from text
        
        Args:
            text: Document text content
            return_top_k: Number of top predictions to return
            threshold: Confidence threshold (overrides default)
        
        Returns:
            Dictionary with classification results
        """
        start_time = time.time()
        
        # Clean text
        cleaned_text = self.text_cleaner.clean_text(text)
        
        if not cleaned_text or len(cleaned_text.strip()) < 10:
            return {
                "success": False,
                "error": "Text too short for classification",
                "document_type": "other",
                "confidence": 0.0,
                "processing_time_ms": (time.time() - start_time) * 1000
            }
        
        # Use fallback if model not loaded
        if not self.is_loaded:
            result = await self._classify_rule_based(cleaned_text, return_top_k)
            result["processing_time_ms"] = (time.time() - start_time) * 1000
            return result
        
        # BERT classification
        try:
            # Tokenize input
            inputs = self.tokenizer(
                cleaned_text,
                max_length=self.max_length,
                padding="max_length",
                truncation=True,
                return_tensors="pt"
            )
            
            # Move to device
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Run inference
            loop = asyncio.get_event_loop()
            with torch.no_grad():
                outputs = await loop.run_in_executor(
                    self.executor,
                    lambda: self.model(**inputs)
                )
            
            # Get probabilities
            logits = outputs.logits
            probabilities = torch.nn.functional.softmax(logits, dim=1)
            probs = probabilities.cpu().numpy()[0]
            
            # Get top K predictions
            top_k_indices = np.argsort(probs)[-return_top_k:][::-1]
            predictions = []
            
            for idx in top_k_indices:
                doc_type = self.DOCUMENT_TYPES[idx]
                confidence = float(probs[idx])
                predictions.append({
                    "document_type": doc_type,
                    "confidence": confidence
                })
            
            # Primary prediction
            primary = predictions[0]
            threshold_val = threshold or self.confidence_threshold
            
            result = {
                "success": True,
                "document_type": primary["document_type"],
                "confidence": primary["confidence"],
                "top_predictions": predictions,
                "meets_threshold": primary["confidence"] >= threshold_val,
                "model_used": "bert",
                "processing_time_ms": (time.time() - start_time) * 1000
            }
            
            return result
        
        except Exception as e:
            logger.error(f"BERT classification failed: {str(e)}")
            fallback_result = await self._classify_rule_based(cleaned_text, return_top_k)
            fallback_result["processing_time_ms"] = (time.time() - start_time) * 1000
            fallback_result["fallback_used"] = True
            return fallback_result
    
    async def _classify_rule_based(
        self,
        text: str,
        return_top_k: int = 3
    ) -> Dict[str, Any]:
        """Rule-based fallback classification using keywords"""
        text_lower = text.lower()
        
        # Count keyword matches for each document type
        scores = {}
        for doc_type, keywords in self.keyword_map.items():
            score = sum(1 for keyword in keywords if keyword in text_lower)
            scores[doc_type] = score
        
        # Normalize scores
        total = sum(scores.values())
        if total > 0:
            for doc_type in scores:
                scores[doc_type] = scores[doc_type] / total
        else:
            # No matches found
            scores = {doc_type: 0.0 for doc_type in self.keyword_map}
            scores["other"] = 1.0
        
        # Get top K
        sorted_types = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        predictions = [
            {"document_type": doc_type, "confidence": score}
            for doc_type, score in sorted_types[:return_top_k]
        ]
        
        return {
            "success": True,
            "document_type": predictions[0]["document_type"],
            "confidence": predictions[0]["confidence"],
            "top_predictions": predictions,
            "meets_threshold": predictions[0]["confidence"] >= self.confidence_threshold,
            "model_used": "rule_based_fallback"
        }
    
    async def batch_classify(
        self,
        texts: List[str],
        return_top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Classify multiple documents in batch
        
        Args:
            texts: List of document texts
            return_top_k: Number of top predictions per document
        
        Returns:
            List of classification results
        """
        tasks = [self.classify(text, return_top_k) for text in texts]
        results = await asyncio.gather(*tasks)
        return results
    
    async def fine_tune(
        self,
        training_texts: List[str],
        training_labels: List[str],
        validation_texts: Optional[List[str]] = None,
        validation_labels: Optional[List[str]] = None,
        epochs: int = 3,
        batch_size: int = 8,
        learning_rate: float = 2e-5
    ) -> Dict[str, Any]:
        """
        Fine-tune BERT model on custom data
        
        Args:
            training_texts: List of training documents
            training_labels: List of document type labels
            validation_texts: Optional validation texts
            validation_labels: Optional validation labels
            epochs: Number of training epochs
            batch_size: Training batch size
            learning_rate: Learning rate
        
        Returns:
            Training results and metrics
        """
        if not self.is_loaded:
            return {"success": False, "error": "BERT model not loaded"}
        
        # Convert labels to IDs
        label_ids = [self.TYPE_TO_ID[label] for label in training_labels]
        
        # Tokenize training data
        train_encodings = self.tokenizer(
            training_texts,
            truncation=True,
            padding=True,
            max_length=self.max_length,
            return_tensors="pt"
        )
        
        # Create PyTorch dataset
        train_dataset = torch.utils.data.TensorDataset(
            train_encodings["input_ids"],
            train_encodings["attention_mask"],
            torch.tensor(label_ids)
        )
        
        train_loader = torch.utils.data.DataLoader(
            train_dataset, batch_size=batch_size, shuffle=True
        )
        
        # Setup optimizer
        optimizer = AdamW(self.model.parameters(), lr=learning_rate)
        total_steps = len(train_loader) * epochs
        scheduler = get_linear_schedule_with_warmup(
            optimizer,
            num_warmup_steps=0,
            num_training_steps=total_steps
        )
        
        # Training loop
        self.model.train()
        training_losses = []
        
        for epoch in range(epochs):
            epoch_loss = 0
            for batch in train_loader:
                optimizer.zero_grad()
                input_ids, attention_mask, labels = batch
                input_ids = input_ids.to(self.device)
                attention_mask = attention_mask.to(self.device)
                labels = labels.to(self.device)
                
                outputs = self.model(
                    input_ids,
                    attention_mask=attention_mask,
                    labels=labels
                )
                
                loss = outputs.loss
                loss.backward()
                optimizer.step()
                scheduler.step()
                
                epoch_loss += loss.item()
            
            avg_loss = epoch_loss / len(train_loader)
            training_losses.append(avg_loss)
            logger.info(f"Epoch {epoch + 1}/{epochs}, Loss: {avg_loss:.4f}")
        
        self.model.eval()
        
        # Validate if validation data provided
        validation_metrics = None
        if validation_texts and validation_labels:
            validation_metrics = await self._validate(
                validation_texts, validation_labels
            )
        
        # Save fine-tuned model
        model_save_path = Path(settings.BERT_MODEL_PATH) / "fine_tuned"
        model_save_path.mkdir(parents=True, exist_ok=True)
        self.model.save_pretrained(str(model_save_path))
        self.tokenizer.save_pretrained(str(model_save_path))
        
        return {
            "success": True,
            "epochs_completed": epochs,
            "training_losses": training_losses,
            "final_loss": training_losses[-1] if training_losses else None,
            "validation_metrics": validation_metrics,
            "model_saved_at": str(model_save_path)
        }
    
    async def _validate(
        self,
        texts: List[str],
        true_labels: List[str]
    ) -> Dict[str, float]:
        """Validate model performance"""
        predictions = await self.batch_classify(texts)
        
        correct = 0
        for pred, true in zip(predictions, true_labels):
            if pred["document_type"] == true:
                correct += 1
        
        accuracy = correct / len(texts) if texts else 0
        
        return {
            "accuracy": accuracy,
            "total_samples": len(texts),
            "correct_predictions": correct
        }
    
    async def get_model_info(self) -> Dict[str, Any]:
        """Get model information"""
        info = {
            "model_name": self.model_name,
            "device": str(self.device),
            "is_loaded": self.is_loaded,
            "max_sequence_length": self.max_length,
            "num_classes": len(self.DOCUMENT_TYPES),
            "document_types": list(self.DOCUMENT_TYPES.values()),
            "confidence_threshold": self.confidence_threshold
        }
        
        if self.is_loaded and self.model:
            # Count parameters
            total_params = sum(p.numel() for p in self.model.parameters())
            trainable_params = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
            
            info.update({
                "total_parameters": total_params,
                "trainable_parameters": trainable_params,
                "model_size_mb": total_params * 4 / (1024 * 1024)  # Approximate
            })
        
        return info
    
    def get_confidence_score(self, text: str) -> float:
        """
        Get confidence score for classification (synchronous)
        
        Args:
            text: Document text
        
        Returns:
            Confidence score between 0 and 1
        """
        import asyncio
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.classify(text))
            return result.get("confidence", 0.0)
        except:
            return 0.0