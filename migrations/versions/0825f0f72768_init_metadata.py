"""init_metadata

Revision ID: 0825f0f72768
Revises: 
Create Date: 2026-08-30 18:39:38.143684

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = '0825f0f72768'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'pipeline_runs',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('start_time', sa.DateTime(), nullable=False),
        sa.Column('end_time', sa.DateTime(), nullable=True),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'data_quality_results',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('run_id', sa.String(), nullable=False),
        sa.Column('rule_name', sa.String(), nullable=False),
        sa.Column('status', sa.String(), nullable=False),
        sa.Column('pass_rate', sa.Float(), nullable=True),
        sa.Column('details', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['run_id'], ['pipeline_runs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'ingestion_events',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('run_id', sa.String(), nullable=False),
        sa.Column('resource_type', sa.String(), nullable=False),
        sa.Column('count', sa.Integer(), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['pipeline_runs.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'lineage_mappings',
        sa.Column('id', sa.String(), nullable=False),
        sa.Column('business_domain', sa.String(), nullable=False),
        sa.Column('business_entity', sa.String(), nullable=False),
        sa.Column('business_attribute', sa.String(), nullable=False),
        sa.Column('fhir_resource', sa.String(), nullable=False),
        sa.Column('fhir_element', sa.String(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('lineage_mappings')
    op.drop_table('ingestion_events')
    op.drop_table('data_quality_results')
    op.drop_table('pipeline_runs')
