"""
Add image_url to menu_sections and price_override to menu_section_items (idempotent)

Revision ID: 20250814_01
Revises: b7c9e1d2f3a4
Create Date: 2025-08-14
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250814_01'
down_revision = 'b7c9e1d2f3a4'
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
    # menu_sections.image_url
    if not column_exists(bind, 'menu_sections', 'image_url'):
        op.add_column('menu_sections', sa.Column('image_url', sa.String(length=300), nullable=True))
    # menu_section_items.price_override
    if not column_exists(bind, 'menu_section_items', 'price_override'):
        op.add_column('menu_section_items', sa.Column('price_override', sa.Numeric(12, 2), nullable=True))


def downgrade():
    bind = op.get_bind()
    # Drop only if exists (best-effort)
    try:
        if column_exists(bind, 'menu_section_items', 'price_override'):
            op.drop_column('menu_section_items', 'price_override')
    except Exception:
        pass
    try:
        if column_exists(bind, 'menu_sections', 'image_url'):
            op.drop_column('menu_sections', 'image_url')
    except Exception:
        pass

