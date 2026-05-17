"""
Tests for Document Service
"""

import pytest
from unittest.mock import patch, AsyncMock, MagicMock
from pathlib import Path
from datetime import datetime


class TestDocumentService:
    """Test cases for document service"""
    
    @pytest.mark.asyncio
    async def test_upload_document(self, document_service, mock_file, temp_upload_dir):
        """Test document upload"""
        document = await document_service.upload_document(
            file=mock_file,
            user_id=1,
            title="Test Document",
            description="Test description"
        )
        
        assert document is not None
        assert document.filename == "test.pdf"
        assert document.user_id == 1
        assert document.title == "Test Document"
    
    @pytest.mark.asyncio
    async def test_get_document(self, document_service, db_session, sample_document):
        """Test get document by ID"""
        # Add document to DB
        db_session.add(sample_document)
        await db_session.commit()
        
        retrieved = await document_service.get_document(sample_document.id, 1)
        
        assert retrieved is not None
        assert retrieved.id == sample_document.id
    
    @pytest.mark.asyncio
    async def test_get_document_not_found(self, document_service):
        """Test get non-existent document"""
        retrieved = await document_service.get_document(99999, 1)
        
        assert retrieved is None
    
    @pytest.mark.asyncio
    async def test_list_documents(self, document_service, db_session, sample_documents):
        """Test list documents with pagination"""
        # Add multiple documents
        for doc in sample_documents:
            db_session.add(doc)
        await db_session.commit()
        
        documents, total = await document_service.list_documents(
            user_id=1,
            offset=0,
            limit=10
        )
        
        assert len(documents) <= len(sample_documents)
        assert total >= len(sample_documents)
    
    @pytest.mark.asyncio
    async def test_list_documents_with_filters(self, document_service, db_session, sample_documents):
        """Test list documents with filters"""
        for doc in sample_documents:
            db_session.add(doc)
        await db_session.commit()
        
        documents, total = await document_service.list_documents(
            user_id=1,
            document_type="invoice",
            offset=0,
            limit=10
        )
        
        for doc in documents:
            assert doc.document_type == "invoice"
    
    @pytest.mark.asyncio
    async def test_update_document(self, document_service, db_session, sample_document):
        """Test update document metadata"""
        db_session.add(sample_document)
        await db_session.commit()
        
        updated = await document_service.update_document(
            document_id=sample_document.id,
            user_id=1,
            title="Updated Title",
            description="Updated Description"
        )
        
        assert updated is not None
        assert updated.title == "Updated Title"
        assert updated.description == "Updated Description"
    
    @pytest.mark.asyncio
    async def test_delete_document(self, document_service, db_session, sample_document):
        """Test delete document"""
        db_session.add(sample_document)
        await db_session.commit()
        
        result = await document_service.delete_document(sample_document.id, 1)
        
        assert result is True
        
        # Verify soft delete
        deleted_doc = await document_service.get_document(sample_document.id, 1)
        assert deleted_doc is None
    
    @pytest.mark.asyncio
    async def test_update_document_status(self, document_service, db_session, sample_document):
        """Test update document status"""
        db_session.add(sample_document)
        await db_session.commit()
        
        updated = await document_service.update_document_status(
            document_id=sample_document.id,
            status="processed"
        )
        
        assert updated is not None
        assert updated.status == "processed"
    
    @pytest.mark.asyncio
    async def test_get_user_stats(self, document_service, db_session, sample_documents):
        """Test get user statistics"""
        for doc in sample_documents:
            db_session.add(doc)
        await db_session.commit()
        
        stats = await document_service.get_user_stats(user_id=1)
        
        assert "total_documents" in stats
        assert "documents_by_type" in stats
        assert "total_storage_mb" in stats
    
    @pytest.mark.asyncio
    async def test_search_documents(self, document_service, db_session, sample_documents):
        """Test search documents"""
        for doc in sample_documents:
            db_session.add(doc)
        await db_session.commit()
        
        results = await document_service.search_documents(
            query="test",
            user_id=1,
            limit=10
        )
        
        assert isinstance(results, list)
    
    @pytest.mark.asyncio
    async def test_reprocess_document(self, document_service, db_session, sample_document):
        """Test reprocess document"""
        db_session.add(sample_document)
        await db_session.commit()
        
        task_id = await document_service.reprocess_document(sample_document.id, 1)
        
        assert task_id is not None
        assert "reprocess" in task_id


# Fixtures
@pytest.fixture
def document_service(db_session, mock_cache_service):
    """Create document service instance"""
    from app.services.document_service import DocumentService
    return DocumentService(db_session, mock_cache_service)


@pytest.fixture
def mock_file():
    """Create mock upload file"""
    from fastapi import UploadFile
    from io import BytesIO
    
    file = MagicMock(spec=UploadFile)
    file.filename = "test.pdf"
    file.size = 1024
    file.content_type = "application/pdf"
    file.read = AsyncMock(return_value=b"test content")
    return file


@pytest.fixture
def sample_document():
    """Create sample document model"""
    from app.database.models.document import Document
    
    return Document(
        filename="test.pdf",
        file_path="/tmp/test.pdf",
        file_size=1024,
        file_type="application/pdf",
        title="Test Document",
        user_id=1,
        status="uploaded",
        created_at=datetime.now(),
        updated_at=datetime.now()
    )


@pytest.fixture
def sample_documents():
    """Create multiple sample documents"""
    from app.database.models.document import Document
    
    documents = []
    for i in range(5):
        doc = Document(
            filename=f"test_{i}.pdf",
            file_path=f"/tmp/test_{i}.pdf",
            file_size=1024,
            file_type="application/pdf",
            title=f"Test Document {i}",
            document_type="invoice" if i % 2 == 0 else "contract",
            user_id=1,
            status="uploaded" if i < 3 else "processed",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        documents.append(doc)
    
    return documents