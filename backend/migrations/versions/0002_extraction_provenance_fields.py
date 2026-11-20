"""Add source_question_label, extraction_status, extraction_warnings, source_page_start, source_page_end to questions.

Revision ID: 0002_extraction_provenance_fields
Revises: 0001_initial_schema
Create Date: 2026-11-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_extraction_provenance_fields"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("questions") as batch_op:
        batch_op.add_column(sa.Column("source_question_label", sa.String(length=32), nullable=False, server_default="UNKNOWN"))
        batch_op.add_column(sa.Column("extraction_status", sa.String(length=32), nullable=False, server_default="uncertain"))
        batch_op.add_column(sa.Column("extraction_warnings", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("source_page_start", sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column("source_page_end", sa.Integer(), nullable=True))

    # Backfill page start/end from existing page_number and flag legacy unlabeled rows for review
    op.execute("UPDATE questions SET source_page_start = COALESCE(source_page_start, page_number), source_page_end = COALESCE(source_page_end, page_number);")
    op.execute("UPDATE questions SET needs_human_review = 1, extraction_status = 'uncertain' WHERE source_question_label = 'UNKNOWN';")


def downgrade() -> None:
    with op.batch_alter_table("questions") as batch_op:
        batch_op.drop_column("source_page_end")
        batch_op.drop_column("source_page_start")
        batch_op.drop_column("extraction_warnings")
        batch_op.drop_column("extraction_status")
        batch_op.drop_column("source_question_label")
