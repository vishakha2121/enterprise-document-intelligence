"""
Initial Migration
Creates all base tables for the Document Intelligence Platform

Revision ID: 001_initial_migration
Revises: 
Create Date: 2024-01-15 10:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001_initial_migration'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create all base tables"""
    
    # Create users table
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('username', sa.String(length=50), nullable=False),
        sa.Column('email', sa.String(length=100), nullable=False),
        sa.Column('full_name', sa.String(length=100), nullable=True),
        sa.Column('hashed_password', sa.String(length=255), nullable=False),
        sa.Column('role', sa.Enum('ADMIN', 'ANALYST', 'VIEWER', 'TRAINER', name='userrole'), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('last_login', sa.DateTime(), nullable=True),
        sa.Column('password_changed_at', sa.DateTime(), nullable=True),
        sa.Column('api_key', sa.String(length=64), nullable=True),
        sa.Column('rate_limit', sa.Integer(), nullable=True, server_default='100'),
        sa.Column('preferences', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('api_key'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username')
    )
    
    # Create indexes for users table
    op.create_index('idx_users_username', 'users', ['username'])
    op.create_index('idx_users_email', 'users', ['email'])
    op.create_index('idx_users_role', 'users', ['role'])
    op.create_index('idx_users_api_key', 'users', ['api_key'])
    
    # Create documents table
    op.create_table(
        'documents',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('file_path', sa.String(length=500), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('file_type', sa.String(length=100), nullable=False),
        sa.Column('file_hash', sa.String(length=64), nullable=True),
        sa.Column('document_type', sa.String(length=50), nullable=True),
        sa.Column('classification_confidence', sa.Float(), nullable=True),
        sa.Column('classification_model', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='uploaded'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('processed_at', sa.DateTime(), nullable=True),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
        sa.Column('tags', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('is_deleted', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('deleted_at', sa.DateTime(), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for documents table
    op.create_index('idx_documents_user_id', 'documents', ['user_id'])
    op.create_index('idx_documents_status', 'documents', ['status'])
    op.create_index('idx_documents_document_type', 'documents', ['document_type'])
    op.create_index('idx_documents_created_at', 'documents', ['created_at'])
    op.create_index('idx_documents_is_deleted', 'documents', ['is_deleted'])
    op.create_index('idx_documents_file_hash', 'documents', ['file_hash'])
    
    # Create extraction_results table
    op.create_table(
        'extraction_results',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('extraction_type', sa.String(length=50), nullable=False),
        sa.Column('extracted_data', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('validated_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('confidence_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('field_confidences', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('ocr_text', sa.Text(), nullable=True),
        sa.Column('ocr_engine', sa.String(length=50), nullable=True),
        sa.Column('processing_time_ms', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('ocr_time_ms', sa.Integer(), nullable=True),
        sa.Column('nlp_time_ms', sa.Integer(), nullable=True),
        sa.Column('is_validated', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('validated_at', sa.DateTime(), nullable=True),
        sa.Column('validated_by', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='completed'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for extraction_results table
    op.create_index('idx_extraction_document_id', 'extraction_results', ['document_id'])
    op.create_index('idx_extraction_user_id', 'extraction_results', ['user_id'])
    op.create_index('idx_extraction_created_at', 'extraction_results', ['created_at'])
    op.create_index('idx_extraction_confidence', 'extraction_results', ['confidence_score'])
    
    # Create fraud_logs table
    op.create_table(
        'fraud_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('document_id', sa.Integer(), nullable=False),
        sa.Column('risk_score', sa.Float(), nullable=False, server_default='0.0'),
        sa.Column('risk_level', sa.String(length=20), nullable=False),
        sa.Column('fraud_type', sa.String(length=50), nullable=True),
        sa.Column('fraud_subtype', sa.String(length=50), nullable=True),
        sa.Column('detection_methods', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('evidence', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='[]'),
        sa.Column('rule_violations', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('anomalies', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('alert_status', sa.String(length=20), nullable=False, server_default='active'),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_by', sa.Integer(), nullable=True),
        sa.Column('resolution_notes', sa.Text(), nullable=True),
        sa.Column('processing_time_ms', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for fraud_logs table
    op.create_index('idx_fraud_document_id', 'fraud_logs', ['document_id'])
    op.create_index('idx_fraud_risk_score', 'fraud_logs', ['risk_score'])
    op.create_index('idx_fraud_risk_level', 'fraud_logs', ['risk_level'])
    op.create_index('idx_fraud_alert_status', 'fraud_logs', ['alert_status'])
    op.create_index('idx_fraud_created_at', 'fraud_logs', ['created_at'])
    
    # Create audit_logs table
    op.create_table(
        'audit_logs',
        sa.Column('id', sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('username', sa.String(length=50), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
        sa.Column('user_agent', sa.String(length=500), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('resource_type', sa.String(length=50), nullable=True),
        sa.Column('resource_id', sa.Integer(), nullable=True),
        sa.Column('resource_name', sa.String(length=255), nullable=True),
        sa.Column('details', postgresql.JSON(astext_type=sa.Text()), nullable=False, server_default='{}'),
        sa.Column('changes', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='success'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('request_method', sa.String(length=10), nullable=True),
        sa.Column('request_path', sa.String(length=500), nullable=True),
        sa.Column('request_query', sa.String(length=500), nullable=True),
        sa.Column('session_id', sa.String(length=100), nullable=True),
        sa.Column('correlation_id', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('now()')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for audit_logs table
    op.create_index('idx_audit_user_id', 'audit_logs', ['user_id'])
    op.create_index('idx_audit_action', 'audit_logs', ['action'])
    op.create_index('idx_audit_created_at', 'audit_logs', ['created_at'])
    op.create_index('idx_audit_resource', 'audit_logs', ['resource_type', 'resource_id'])
    op.create_index('idx_audit_correlation_id', 'audit_logs', ['correlation_id'])
    
    # Create document_type enum type
    op.execute("CREATE TYPE document_type_enum AS ENUM ('invoice', 'contract', 'form', 'receipt', 'report', 'other')")
    
    # Create processing_status enum type
    op.execute("CREATE TYPE processing_status_enum AS ENUM ('uploaded', 'processing', 'processed', 'failed', 'archived', 'deleted')")


def downgrade() -> None:
    """Drop all tables"""
    
    # Drop indexes first
    op.drop_index('idx_audit_correlation_id', table_name='audit_logs')
    op.drop_index('idx_audit_resource', table_name='audit_logs')
    op.drop_index('idx_audit_created_at', table_name='audit_logs')
    op.drop_index('idx_audit_action', table_name='audit_logs')
    op.drop_index('idx_audit_user_id', table_name='audit_logs')
    
    op.drop_index('idx_fraud_created_at', table_name='fraud_logs')
    op.drop_index('idx_fraud_alert_status', table_name='fraud_logs')
    op.drop_index('idx_fraud_risk_level', table_name='fraud_logs')
    op.drop_index('idx_fraud_risk_score', table_name='fraud_logs')
    op.drop_index('idx_fraud_document_id', table_name='fraud_logs')
    
    op.drop_index('idx_extraction_confidence', table_name='extraction_results')
    op.drop_index('idx_extraction_created_at', table_name='extraction_results')
    op.drop_index('idx_extraction_user_id', table_name='extraction_results')
    op.drop_index('idx_extraction_document_id', table_name='extraction_results')
    
    op.drop_index('idx_documents_file_hash', table_name='documents')
    op.drop_index('idx_documents_is_deleted', table_name='documents')
    op.drop_index('idx_documents_created_at', table_name='documents')
    op.drop_index('idx_documents_document_type', table_name='documents')
    op.drop_index('idx_documents_status', table_name='documents')
    op.drop_index('idx_documents_user_id', table_name='documents')
    
    op.drop_index('idx_users_api_key', table_name='users')
    op.drop_index('idx_users_role', table_name='users')
    op.drop_index('idx_users_email', table_name='users')
    op.drop_index('idx_users_username', table_name='users')
    
    # Drop tables
    op.drop_table('audit_logs')
    op.drop_table('fraud_logs')
    op.drop_table('extraction_results')
    op.drop_table('documents')
    op.drop_table('users')
    
    # Drop enum types
    op.execute("DROP TYPE processing_status_enum")
    op.execute("DROP TYPE document_type_enum")
    op.execute("DROP TYPE userrole")