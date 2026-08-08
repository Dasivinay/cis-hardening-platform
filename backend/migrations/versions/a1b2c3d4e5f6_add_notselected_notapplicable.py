"""add notselected/notapplicable control counts to scans

Revision ID: a1b2c3d4e5f6
Revises: e6cb39ff374f
Create Date: 2026-08-03 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'e6cb39ff374f'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('scans', sa.Column('notapplicable_controls', sa.Integer(), nullable=True, server_default='0'))
    op.add_column('scans', sa.Column('notselected_controls', sa.Integer(), nullable=True, server_default='0'))


def downgrade():
    op.drop_column('scans', 'notselected_controls')
    op.drop_column('scans', 'notapplicable_controls')
