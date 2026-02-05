"""ربط القيود بالدفعات والفواتير — مصدر الحقيقة الوحيد من القيود المنشورة

Revision ID: je_pay_inv_01
Revises: acc_usage_01
Create Date: 2026-02-02

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = 'je_pay_inv_01'
down_revision = 'acc_usage_01'
branch_labels = None
depends_on = None


def _column_exists(conn, table, column):
    if conn.dialect.name == 'sqlite':
        result = conn.execute(sa.text(f"PRAGMA table_info({table})"))
        return any(row[1] == column for row in result)
    from sqlalchemy import inspect
    return column in [c['name'] for c in inspect(conn).get_columns(table)]


def upgrade():
    conn = op.get_bind()
    if not _column_exists(conn, 'journal_entries', 'payment_method'):
        op.add_column('journal_entries', sa.Column('payment_method', sa.String(20), nullable=True))
    if not _column_exists(conn, 'journal_lines', 'invoice_id'):
        op.add_column('journal_lines', sa.Column('invoice_id', sa.Integer(), nullable=True))
    if not _column_exists(conn, 'journal_lines', 'invoice_type'):
        op.add_column('journal_lines', sa.Column('invoice_type', sa.String(20), nullable=True))
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_journal_lines_invoice_id ON journal_lines (invoice_id)"))
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_journal_lines_invoice_type ON journal_lines (invoice_type)"))


def downgrade():
    op.execute(text("DROP INDEX IF EXISTS ix_journal_lines_invoice_type"))
    op.execute(text("DROP INDEX IF EXISTS ix_journal_lines_invoice_id"))
    conn = op.get_bind()
    if _column_exists(conn, 'journal_lines', 'invoice_type'):
        op.drop_column('journal_lines', 'invoice_type')
    if _column_exists(conn, 'journal_lines', 'invoice_id'):
        op.drop_column('journal_lines', 'invoice_id')
    if _column_exists(conn, 'journal_entries', 'payment_method'):
        op.drop_column('journal_entries', 'payment_method')
