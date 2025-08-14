"""
Merge heads for POS and permissions branches

Revision ID: b7c9e1d2f3a4
Revises: 6d694fcb64fd, 8f1a2b3c4d5e
Create Date: 2025-08-13
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b7c9e1d2f3a4'
down_revision = ('6d694fcb64fd', '8f1a2b3c4d5e')
branch_labels = None
depends_on = None

def upgrade():
    # Merge only; no ops
    pass

def downgrade():
    # Merge only; no ops
    pass

