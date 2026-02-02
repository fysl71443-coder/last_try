"""merge exp_liab and salary_extra

Revision ID: d79c61656053
Revises: exp_liab_01, salary_extra_01
Create Date: 2026-02-01 18:21:35.383220

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd79c61656053'
down_revision = ('exp_liab_01', 'salary_extra_01')
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
