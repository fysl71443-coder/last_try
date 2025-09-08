"""add missing columns to settings

Revision ID: 20250908_01
Revises: 20250816_02
Create Date: 2025-09-08 21:30:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20250908_01'
down_revision = '20250816_02'
branch_labels = None
depends_on = None

def upgrade():
    # ثيم افتراضي
    op.add_column('settings', sa.Column('default_theme', sa.String(length=50), nullable=True))

    # China Town
    op.add_column('settings', sa.Column('china_town_void_password', sa.String(length=50), nullable=True))
    op.add_column('settings', sa.Column('china_town_vat_rate', sa.Numeric(5, 2), nullable=True))
    op.add_column('settings', sa.Column('china_town_discount_rate', sa.Numeric(5, 2), nullable=True))

    # Palace India
    op.add_column('settings', sa.Column('place_india_void_password', sa.String(length=50), nullable=True))
    op.add_column('settings', sa.Column('place_india_vat_rate', sa.Numeric(5, 2), nullable=True))
    op.add_column('settings', sa.Column('place_india_discount_rate', sa.Numeric(5, 2), nullable=True))

    # إعدادات الطابعة
    op.add_column('settings', sa.Column('receipt_paper_width', sa.Integer(), nullable=True))
    op.add_column('settings', sa.Column('receipt_margin_top_mm', sa.Integer(), nullable=True))
    op.add_column('settings', sa.Column('receipt_margin_bottom_mm', sa.Integer(), nullable=True))
    op.add_column('settings', sa.Column('receipt_margin_left_mm', sa.Integer(), nullable=True))
    op.add_column('settings', sa.Column('receipt_margin_right_mm', sa.Integer(), nullable=True))
    op.add_column('settings', sa.Column('receipt_font_size', sa.Integer(), nullable=True))

    # إعدادات عرض الفاتورة
    op.add_column('settings', sa.Column('receipt_show_logo', sa.Boolean(), nullable=True, server_default=sa.text('true')))
    op.add_column('settings', sa.Column('receipt_show_tax_number', sa.Boolean(), nullable=True, server_default=sa.text('true')))
    op.add_column('settings', sa.Column('receipt_footer_text', sa.Text(), nullable=True))
    op.add_column('settings', sa.Column('logo_url', sa.Text(), nullable=True))

def downgrade():
    op.drop_column('settings', 'logo_url')
    op.drop_column('settings', 'receipt_footer_text')
    op.drop_column('settings', 'receipt_show_tax_number')
    op.drop_column('settings', 'receipt_show_logo')
    op.drop_column('settings', 'receipt_font_size')
    op.drop_column('settings', 'receipt_margin_right_mm')
    op.drop_column('settings', 'receipt_margin_left_mm')
    op.drop_column('settings', 'receipt_margin_bottom_mm')
    op.drop_column('settings', 'receipt_margin_top_mm')
    op.drop_column('settings', 'receipt_paper_width')
    op.drop_column('settings', 'place_india_discount_rate')
    op.drop_column('settings', 'place_india_vat_rate')
    op.drop_column('settings', 'place_india_void_password')
    op.drop_column('settings', 'china_town_discount_rate')
    op.drop_column('settings', 'china_town_vat_rate')
    op.drop_column('settings', 'china_town_void_password')
    op.drop_column('settings', 'default_theme')
