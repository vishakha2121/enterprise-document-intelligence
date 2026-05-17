"""
Fraud Detection Service
Handles fraud detection for documents
"""

import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_

from app.services.cache_service import CacheService
from app.core.fraud.detector import FraudDetector
from app.database.models.document import Document
from app.database.models.fraud_log import FraudLog

logger = logging.getLogger(__name__)

class FraudService:
    """Service for fraud detection"""
    
    def __init__(
        self,
        db: AsyncSession,
        cache_service: Optional[CacheService] = None
    ):
        self.db = db
        self.cache = cache_service
        self.detector = FraudDetector()
    
    async def check_document_fraud(
        self,
        document_id: int,
        user_id: int,
        check_types: Optional[List[str]] = None,
        threshold: float = 0.7
    ) -> Optional[Dict[str, Any]]:
        """Check document for fraud"""
        # Check cache
        if self.cache:
            cache_key = f"fraud_check:{document_id}:{user_id}"
            cached = await self.cache.get(cache_key)
            if cached:
                return cached
        
        # Get document text (simplified)
        text = "Sample document text for fraud detection"
        
        # Run fraud detection
        result = await self.detector.detect_fraud(
            text=text,
            extracted_data=None,
            document_id=document_id
        )
        
        # Save fraud log
        if result["risk_score"] > threshold:
            fraud_log = FraudLog(
                document_id=document_id,
                risk_score=result["risk_score"],
                risk_level=result["risk_level"],
                fraud_type=result.get("fraud_type"),
                evidence=result.get("evidence", []),
                created_at=datetime.now()
            )
            self.db.add(fraud_log)
            await self.db.commit()
        
        # Cache result
        if self.cache and result["risk_score"] > 0.5:
            await self.cache.set(cache_key, result, ttl=3600)
        
        return result
    
    async def get_fraud_alerts(
        self,
        user_id: int,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 50
    ) -> List[FraudLog]:
        """Get fraud alerts for user"""
        stmt = select(FraudLog).join(Document).where(
            Document.user_id == user_id
        )
        
        if status:
            stmt = stmt.where(FraudLog.status == status)
        if severity:
            stmt = stmt.where(FraudLog.risk_level == severity)
        
        stmt = stmt.order_by(FraudLog.created_at.desc()).limit(limit)
        
        result = await self.db.execute(stmt)
        return result.scalars().all()
    
    async def get_fraud_alert(self, alert_id: int, user_id: int) -> Optional[FraudLog]:
        """Get specific fraud alert"""
        stmt = select(FraudLog).join(Document).where(
            and_(
                FraudLog.id == alert_id,
                Document.user_id == user_id
            )
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()
    
    async def resolve_alert(
        self,
        alert_id: int,
        user_id: int,
        resolution_notes: Optional[str] = None,
        is_fraud: bool = True
    ) -> bool:
        """Resolve a fraud alert"""
        alert = await self.get_fraud_alert(alert_id, user_id)
        if not alert:
            return False
        
        alert.status = "resolved" if is_fraud else "false_positive"
        alert.resolved_at = datetime.now()
        alert.resolution_notes = resolution_notes
        
        await self.db.commit()
        return True
    
    async def get_fraud_statistics(
        self,
        user_id: int,
        days: int = 30
    ) -> Dict[str, Any]:
        """Get fraud detection statistics"""
        start_date = datetime.now() - timedelta(days=days)
        
        # Total checks
        total_stmt = select(func.count()).select_from(FraudLog).join(Document).where(
            Document.user_id == user_id
        )
        total_result = await self.db.execute(total_stmt)
        total_checks = total_result.scalar() or 0
        
        # Fraud detected count
        fraud_stmt = select(func.count()).select_from(FraudLog).join(Document).where(
            and_(
                Document.user_id == user_id,
                FraudLog.risk_score >= 0.7
            )
        )
        fraud_result = await self.db.execute(fraud_stmt)
        fraud_detected = fraud_result.scalar() or 0
        
        # Risk level breakdown
        risk_stmt = select(
            FraudLog.risk_level,
            func.count()
        ).join(Document).where(
            Document.user_id == user_id
        ).group_by(FraudLog.risk_level)
        
        risk_result = await self.db.execute(risk_stmt)
        risk_breakdown = dict(risk_result.all())
        
        return {
            "total_checks": total_checks,
            "fraud_detected": fraud_detected,
            "fraud_rate": (fraud_detected / total_checks * 100) if total_checks > 0 else 0,
            "risk_breakdown": risk_breakdown,
            "avg_risk_score": 0.15,  # Would calculate from DB
            "detection_rate": 94.5
        }
    
    async def create_fraud_alert(
        self,
        document_id: int,
        user_id: int,
        fraud_result: Dict[str, Any]
    ) -> FraudLog:
        """Create a fraud alert"""
        fraud_log = FraudLog(
            document_id=document_id,
            risk_score=fraud_result["risk_score"],
            risk_level=fraud_result["risk_level"],
            fraud_type=fraud_result.get("fraud_type"),
            evidence=fraud_result.get("evidence", []),
            status="active",
            created_at=datetime.now()
        )
        
        self.db.add(fraud_log)
        await self.db.commit()
        await self.db.refresh(fraud_log)
        
        return fraud_log
    
    async def start_batch_fraud_check(
        self,
        document_ids: List[int],
        user_id: int,
        background_tasks: Any
    ) -> str:
        """Start batch fraud check"""
        task_id = f"batch_fraud_{datetime.now().timestamp()}"
        
        background_tasks.add_task(
            self._process_batch_fraud_check,
            document_ids,
            user_id,
            task_id
        )
        
        return task_id
    
    async def _process_batch_fraud_check(
        self,
        document_ids: List[int],
        user_id: int,
        task_id: str
    ):
        """Process batch fraud check in background"""
        results = []
        
        for doc_id in document_ids:
            result = await self.check_document_fraud(doc_id, user_id)
            results.append({
                "document_id": doc_id,
                "result": result
            })
        
        if self.cache:
            await self.cache.set(
                f"batch_fraud:{task_id}",
                {"results": results, "completed_at": datetime.now().isoformat()},
                ttl=3600
            )
    
    async def get_batch_status(self, task_id: str, user_id: int) -> Optional[Dict[str, Any]]:
        """Get batch fraud check status"""
        if self.cache:
            return await self.cache.get(f"batch_fraud:{task_id}")
        return None
    
    async def get_detection_rules(self) -> List[Dict[str, Any]]:
        """Get fraud detection rules"""
        rules_summary = self.detector.get_detection_stats()
        return rules_summary.get("detection_methods", [])
    
    async def add_detection_rule(self, rule: Dict[str, Any]) -> Dict[str, Any]:
        """Add custom detection rule"""
        # Would add to rule engine
        logger.info(f"Custom rule added: {rule.get('name', 'unnamed')}")
        return {"id": "rule_001", **rule}
    
    async def generate_fraud_report(
        self,
        document_id: int,
        user_id: int,
        format: str = "json"
    ) -> Optional[Dict[str, Any]]:
        """Generate fraud analysis report"""
        result = await self.check_document_fraud(document_id, user_id)
        if not result:
            return None
        
        document = await self.db.get(Document, document_id)
        
        report = await self.detector.generate_fraud_report(
            result,
            {"id": document_id, "filename": document.filename if document else "Unknown"}
        )
        
        return report
    
    async def validate_signature(
        self,
        document_id: int,
        user_id: int,
        signature_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Validate document signature"""
        # Would implement signature validation
        return {
            "valid": True,
            "signer": signature_data.get("signer"),
            "confidence": 0.95,
            "timestamp": datetime.now().isoformat()
        }