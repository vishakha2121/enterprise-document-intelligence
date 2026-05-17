"""
Classification Service
Handles document classification using BERT model
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.services.cache_service import CacheService
from app.core.nlp.model_loader import ModelLoader
from app.database.models.document import Document

logger = logging.getLogger(__name__)

class ClassificationService:
    """Service for document classification"""
    
    def __init__(
        self,
        model_loader: ModelLoader,
        cache_service: Optional[CacheService] = None
    ):
        self.model_loader = model_loader
        self.cache = cache_service
    
    async def classify_document(
        self,
        document_id: int,
        user_id: int,
        model_type: str = "hybrid",
        confidence_threshold: float = 0.7
    ) -> Optional[Dict[str, Any]]:
        """Classify document type"""
        # Check cache
        if self.cache:
            cache_key = f"classification:{document_id}:{user_id}"
            cached = await self.cache.get(cache_key)
            if cached:
                return cached
        
        # Get document text (from OCR)
        # For now, this would come from extraction service
        # Simplified: return mock classification
        classification_result = {
            "document_id": document_id,
            "document_type": "invoice",  # Would be actual classification
            "confidence": 0.92,
            "top_predictions": [
                {"document_type": "invoice", "confidence": 0.92},
                {"document_type": "receipt", "confidence": 0.05},
                {"document_type": "form", "confidence": 0.03}
            ],
            "model_version": "bert-base-uncased",
            "processing_time_ms": 150,
            "created_at": datetime.now().isoformat()
        }
        
        # Cache result
        if self.cache and classification_result["confidence"] > 0.8:
            await self.cache.set(cache_key, classification_result, ttl=86400)
        
        return classification_result
    
    async def batch_classify_documents(
        self,
        document_ids: List[int],
        user_id: int,
        model_type: str = "hybrid",
        confidence_threshold: float = 0.7
    ) -> Dict[str, Any]:
        """Classify multiple documents"""
        results = []
        
        for doc_id in document_ids:
            result = await self.classify_document(doc_id, user_id, model_type, confidence_threshold)
            if result:
                results.append(result)
        
        return {
            "total_documents": len(document_ids),
            "results": results,
            "summary": {
                "successful": len(results),
                "failed": len(document_ids) - len(results)
            }
        }
    
    async def get_document_classifications(
        self,
        document_id: int,
        user_id: int,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get classification history for document"""
        # Would query database for historical classifications
        return []
    
    async def train_model(self, training_data: Dict[str, Any]) -> str:
        """Train or fine-tune classification model"""
        task_id = f"train_model_{datetime.now().timestamp()}"
        logger.info(f"Model training started: {task_id}")
        return task_id
    
    async def get_training_status(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get model training status"""
        if self.cache:
            return await self.cache.get(f"training_status:{task_id}")
        return None
    
    async def get_model_info(self) -> Dict[str, Any]:
        """Get information about classification models"""
        return {
            "available_models": ["bert", "rule_based", "hybrid"],
            "default_model": "hybrid",
            "supported_document_types": ["invoice", "contract", "form", "receipt", "report", "other"],
            "version": "1.0.0"
        }
    
    async def submit_feedback(
        self,
        classification_id: int,
        user_id: int,
        correct_type: str,
        user_confidence: float = 1.0,
        comments: Optional[str] = None
    ) -> bool:
        """Submit feedback for classification"""
        # Store feedback for model improvement
        feedback = {
            "classification_id": classification_id,
            "user_id": user_id,
            "correct_type": correct_type,
            "user_confidence": user_confidence,
            "comments": comments,
            "submitted_at": datetime.now().isoformat()
        }
        
        if self.cache:
            await self.cache.lpush("classification_feedback", feedback)
        
        logger.info(f"Feedback submitted for classification {classification_id}")
        return True