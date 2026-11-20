"""Initial schema creating all 19 GATE Intelligence tables and pgvector extension.

Revision ID: 0001_initial_schema
Revises: None
Create Date: 2026-11-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("CREATE EXTENSION IF NOT EXISTS vector;")
    from app.models.sql_models import Base
    if Base is not None:
        Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    from app.models.sql_models import Base
    if Base is not None:
        Base.metadata.drop_all(bind=op.get_bind())
