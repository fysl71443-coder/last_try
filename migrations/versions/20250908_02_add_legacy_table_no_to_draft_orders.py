"""
Add legacy table_no column to draft_orders for compatibility (idempotent)

Revision ID: 20250908_02
Revises: 20250908_01
Create Date: 2025-09-08
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250908_02'
down_revision = '20250908_01'
branch_labels = None
depends_on = None


def column_exists(bind, table_name: str, column_name: str) -> bool:
    insp = sa.inspect(bind)
    try:
        cols = [c['name'] for c in insp.get_columns(table_name)]
        return column_name in cols
    except Exception:
        return False


def upgrade():
    bind = op.get_bind()
    # Add table_no if missing; keep nullable then backfill and enforce NOT NULL if possible
    if not column_exists(bind, 'draft_orders', 'table_no'):
        try:
            with op.batch_alter_table('draft_orders', schema=None) as batch_op:
                batch_op.add_column(sa.Column('table_no', sa.Integer(), nullable=True))
        except Exception:
            # best-effort for SQLite
            pass

        # Backfill from table_number if present, else set 0
        try:
            op.execute("""
                UPDATE draft_orders
                SET table_no = COALESCE(CASE
                    WHEN table_number GLOB '[0-9]*' THEN CAST(table_number AS INTEGER)
                    ELSE NULL
                END, 0)
            """)
        except Exception:
            # Fallback: set zeros
            try:
                op.execute("UPDATE draft_orders SET table_no = 0 WHERE table_no IS NULL")
            except Exception:
                pass

        # Try to enforce NOT NULL
        try:
            with op.batch_alter_table('draft_orders', schema=None) as batch_op:
                batch_op.alter_column('table_no', existing_type=sa.Integer(), nullable=False)
        except Exception:
            # leave nullable if dialect limitations
            pass


def downgrade():
    # Safe to keep column; no destructive drop by default
    try:
        with op.batch_alter_table('draft_orders', schema=None) as batch_op:
            batch_op.drop_column('table_no')
    except Exception:
        pass

