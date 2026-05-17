"""
Model Loader for NLP Models
Manages loading, caching, and unloading of ML models
"""

import torch
import logging
from typing import Dict, Any, Optional
from pathlib import Path
import json
import asyncio
from concurrent.futures import ThreadPoolExecutor
import psutil
import gc

from app.config import settings
from app.core.nlp.bert_classifier import BERTClassifier
from app.core.nlp.ner_extractor import NERExtractor

logger = logging.getLogger(__name__)

class ModelLoader:
    """
    Centralized model loader with caching and memory management
    Loads and manages BERT and NER models efficiently
    """
    
    def __init__(self):
        """Initialize model loader"""
        self.models = {}
        self.model_metadata = {}
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        
        # Model configurations
        self.model_configs = {
            "bert_classifier": {
                "class": BERTClassifier,
                "path": settings.BERT_MODEL_PATH,
                "lazy_load": True,
                "memory_mb": 850  # Approximate
            },
            "ner_extractor": {
                "class": NERExtractor,
                "path": settings.NER_MODEL_PATH,
                "lazy_load": True,
                "memory_mb": 500
            }
        }
        
        self.loaded_models = {}
        self.load_times = {}
        
        logger.info(f"Model Loader initialized on {self.device}")
    
    async def load_model(self, model_name: str, force_reload: bool = False) -> Any:
        """
        Load a model by name
        
        Args:
            model_name: Name of the model to load
            force_reload: Force reload even if already loaded
        
        Returns:
            Loaded model instance
        """
        if model_name not in self.model_configs:
            raise ValueError(f"Unknown model: {model_name}")
        
        # Check if already loaded
        if not force_reload and model_name in self.loaded_models:
            logger.info(f"Model {model_name} already loaded, returning cached instance")
            return self.loaded_models[model_name]
        
        # Check memory before loading
        if not self._check_available_memory(self.model_configs[model_name]["memory_mb"]):
            logger.warning(f"Insufficient memory for {model_name}, attempting to free memory")
            await self._free_memory()
        
        # Load model
        try:
            start_time = asyncio.get_event_loop().time()
            
            config = self.model_configs[model_name]
            model_class = config["class"]
            
            # Load in thread pool
            loop = asyncio.get_event_loop()
            model = await loop.run_in_executor(
                self.executor,
                lambda: model_class()
            )
            
            load_time = asyncio.get_event_loop().time() - start_time
            
            self.loaded_models[model_name] = model
            self.load_times[model_name] = load_time
            
            logger.info(f"Model {model_name} loaded in {load_time:.2f} seconds")
            
            return model
        
        except Exception as e:
            logger.error(f"Failed to load model {model_name}: {str(e)}")
            raise
    
    async def get_classifier(self) -> BERTClassifier:
        """Get BERT classifier instance"""
        return await self.load_model("bert_classifier")
    
    async def get_ner_extractor(self) -> NERExtractor:
        """Get NER extractor instance"""
        return await self.load_model("ner_extractor")
    
    async def unload_model(self, model_name: str):
        """
        Unload a model to free memory
        
        Args:
            model_name: Name of the model to unload
        """
        if model_name in self.loaded_models:
            logger.info(f"Unloading model: {model_name}")
            
            # Delete model
            del self.loaded_models[model_name]
            
            # Force garbage collection
            gc.collect()
            
            # Clear CUDA cache if using GPU
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            logger.info(f"Model {model_name} unloaded successfully")
    
    async def _free_memory(self):
        """Free memory by unloading least recently used models"""
        # Simple LRU: unload models in order of loading
        for model_name in list(self.loaded_models.keys()):
            await self.unload_model(model_name)
            if self._check_available_memory(100):  # Check if enough memory
                break
    
    def _check_available_memory(self, required_mb: int) -> bool:
        """Check if enough memory is available"""
        try:
            available_memory = psutil.virtual_memory().available / (1024 * 1024)
            return available_memory > required_mb + 100  # 100MB buffer
        except:
            return True  # Assume enough if can't check
    
    async def get_model_info(self, model_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get information about loaded models
        
        Args:
            model_name: Specific model name (None for all)
        
        Returns:
            Dictionary with model information
        """
        if model_name:
            if model_name not in self.model_configs:
                return {"error": f"Model {model_name} not found"}
            
            return {
                "name": model_name,
                "is_loaded": model_name in self.loaded_models,
                "load_time": self.load_times.get(model_name),
                "config": self.model_configs[model_name],
                "device": str(self.device)
            }
        
        # Return info for all models
        all_models = {}
        for name in self.model_configs:
            all_models[name] = {
                "is_loaded": name in self.loaded_models,
                "load_time": self.load_times.get(name),
                "config": self.model_configs[name]
            }
        
        return {
            "models": all_models,
            "device": str(self.device),
            "memory_available_mb": psutil.virtual_memory().available / (1024 * 1024),
            "cuda_available": torch.cuda.is_available(),
            "cuda_memory_mb": torch.cuda.memory_allocated() / (1024 * 1024) if torch.cuda.is_available() else 0
        }
    
    async def warmup_models(self, model_names: Optional[List[str]] = None):
        """
        Preload models for faster first request
        
        Args:
            model_names: List of models to warm up (None for all)
        """
        if model_names is None:
            model_names = list(self.model_configs.keys())
        
        logger.info(f"Warming up models: {model_names}")
        
        tasks = []
        for model_name in model_names:
            if not self.model_configs[model_name].get("lazy_load", False):
                tasks.append(self.load_model(model_name))
        
        if tasks:
            await asyncio.gather(*tasks)
            logger.info("Model warmup complete")
    
    def is_model_loaded(self, model_name: str) -> bool:
        """Check if a model is currently loaded"""
        return model_name in self.loaded_models
    
    async def reload_model(self, model_name: str) -> Any:
        """
        Reload a model (useful after configuration changes)
        
        Args:
            model_name: Name of the model to reload
        
        Returns:
            Newly loaded model instance
        """
        await self.unload_model(model_name)
        return await self.load_model(model_name, force_reload=True)
    
    def get_model_status(self) -> Dict[str, Any]:
        """
        Get overall model status including memory usage
        
        Returns:
            Dictionary with model status
        """
        total_memory_mb = 0
        for model_name in self.loaded_models:
            total_memory_mb += self.model_configs[model_name]["memory_mb"]
        
        return {
            "models_loaded": len(self.loaded_models),
            "loaded_model_names": list(self.loaded_models.keys()),
            "estimated_memory_usage_mb": total_memory_mb,
            "available_memory_mb": psutil.virtual_memory().available / (1024 * 1024),
            "cpu_percent": psutil.cpu_percent(),
            "device": str(self.device)
        }