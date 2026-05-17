"""
Add Fraud Detection Tables and Enhancements
Adds advanced fraud detection features and indexes

Revision ID: 002_add_fraud_tables
Revises: 001_initial_migration
Create Date: 2024-01-16 10:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '002_add_fraud_tables'
down_revision: Union[str, None] = '001_initial_migration'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add fraud detection enhancements"""
    
    # Add new columns to fraud_logs table
    op.add_column('fraud_logs', sa.Column('investigation_notes', sa.Text(), nullable=True))
    op.add_column('fraud_logs', sa.Column('assigned_to', sa.Integer(), nullable=True))
    op.add_column('fraud_logs', sa.Column('reviewed_at', sa.DateTime(), nullable=True))
    op.add_column('fraud_logs', sa.Column('auto_resolved', sa.Boolean(), nullable=False, server_default='false'))
    
    # Create fraud_rules table for dynamic rules
    op.create_table(
        'fraud_rules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('condition', sa.Text(), nullable=False),
        sa.Column('action', sa.Text(), nullable=True),
        sa.Column('weight', sa.Float(), nullable=False, server_default='1.0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create fraud_patterns table for ML-based detection
    op.create_table(
        'fraud_patterns',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('pattern_name', sa.String(length=100), nullable=False),
        sa.Column('pattern_type', sa.String(length=50), nullable=False),
        sa.Column('pattern_data', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('confidence', sa.Float(), nullable=False),
        sa.Column('detection_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('false_positive_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create fraud_alerts table for real-time alerts
    op.create_table(
        'fraud_alerts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('fraud_log_id', sa.Integer(), nullable=False),
        sa.Column('alert_type', sa.String(length=50), nullable=False),
        sa.Column('severity', sa.String(length=20), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('is_acknowledged', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('acknowledged_by', sa.Integer(), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['fraud_log_id'], ['fraud_logs.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for new tables
    op.create_index('idx_fraud_rules_active', 'fraud_rules', ['is_active'])
    op.create_index('idx_fraud_rules_severity', 'fraud_rules', ['severity'])
    op.create_index('idx_fraud_patterns_type', 'fraud_patterns', ['pattern_type'])
    op.create_index('idx_fraud_patterns_active', 'fraud_patterns', ['is_active'])
    op.create_index('idx_fraud_alerts_fraud_log', 'fraud_alerts', ['fraud_log_id'])
    op.create_index('idx_fraud_alerts_severity', 'fraud_alerts', ['severity'])
    op.create_index('idx_fraud_alerts_unread', 'fraud_alerts', ['is_read', 'created_at'])
    
    # Add fraud_risk_score column to documents table
    op.add_column('documents', sa.Column('fraud_risk_score', sa.Float(), nullable=True))
    op.add_column('documents', sa.Column('fraud_risk_level', sa.String(length=20), nullable=True))
    op.add_column('documents', sa.Column('last_fraud_check', sa.DateTime(), nullable=True))
    
    # Create index for fraud risk on documents
    op.create_index('idx_documents_fraud_risk', 'documents', ['fraud_risk_score'])
    
    # Create document_versions table for version tracking
    op.create_table(
        'document_versions',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('version_number', sa.Integer(), nullable=False),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('file_hash', sa.String(length=64), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('changes_summary', sa.Text(), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('document_id', 'version_number', name='uq_document_version')
    )
    
    # Create index for document versions
    op.create_index('idx_doc_versions_document', 'document_versions', ['document_id'])
    
    # Add duplicate_detection_hash column to documents
    op.add_column('documents', sa.Column('content_hash', sa.String(length=64), nullable=True))
    op.create_index('idx_documents_content_hash', 'documents', ['content_hash'])


def downgrade() -> None:
    """Remove fraud detection enhancements"""
    
    # Drop indexes
    op.drop_index('idx_documents_content_hash', table_name='documents')
    op.drop_index('idx_doc_versions_document', table_name='document_versions')
    op.drop_index('idx_documents_fraud_risk', table_name='documents')
    op.drop_index('idx_fraud_alerts_unread', table_name='fraud_alerts')
    op.drop_index('idx_fraud_alerts_severity', table_name='fraud_alerts')
    op.drop_index('idx_fraud_alerts_fraud_log', table_name='fraud_alerts')
    op.drop_index('idx_fraud_patterns_active', table_name='fraud_patterns')
    op.drop_index('idx_fraud_patterns_type', table_name='fraud_patterns')
    op.drop_index('idx_fraud_rules_severity', table_name='fraud_rules')
    op.drop_index('idx_fraud_rules_active', table_name='fraud_rules')
    
    # Drop tables
    op.drop_table('document_versions')
    op.drop_table('fraud_alerts')
    op.drop_table('fraud_patterns')
    op.drop_table('fraud_rules')
    
    # Drop columns
    op.drop_column('documents', 'content_hash')
    op.drop_column('documents', 'last_fraud_check')
    op.drop_column('documents', 'fraud_risk_level')
    op.drop_column('documents', 'fraud_risk_score')
    op.drop_column('fraud_logs', 'auto_resolved')
    op.drop_column('fraud_logs', 'reviewed_at')
    op.drop_column('fraud_logs', 'assigned_to')
    op.drop_column('fraud_logs', 'investigation_notes')