"""ربط القيود بالدفعات والفواتير — مصدر الحقيقة الوحيد من القيود المنشورة

Revision ID: je_pay_inv_01
Revises: acc_usage_01
Create Date: 2026-02-02

"""
from alembic import op
from sqlalchemy import text


revision = 'je_pay_inv_01'
down_revision = 'acc_usage_01'
branch_labels = None
depends_on = None


def upgrade():
    # journal_entries: طريقة الدفع للقيود الناتجة عن سداد/تحصيل
    op.execute(text("ALTER TABLE journal_entries ADD COLUMN payment_method VARCHAR(20)"))
    # journal_lines: ربط سطر القيد بفاتورة (سداد/تحصيل) لاستخراج المدفوع من القيود فقط
    op.execute(text("ALTER TABLE journal_lines ADD COLUMN invoice_id INTEGER"))
    op.execute(text("ALTER TABLE journal_lines ADD COLUMN invoice_type VARCHAR(20)"))
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_journal_lines_invoice_id ON journal_lines (invoice_id)"))
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_journal_lines_invoice_type ON journal_lines (invoice_type)"))


def downgrade():
    op.execute(text("DROP INDEX IF EXISTS ix_journal_lines_invoice_type"))
    op.execute(text("DROP INDEX IF EXISTS ix_journal_lines_invoice_id"))
    op.execute(text("ALTER TABLE journal_lines DROP COLUMN invoice_type"))
    op.execute(text("ALTER TABLE journal_lines DROP COLUMN invoice_id"))
    op.execute(text("ALTER TABLE journal_entries DROP COLUMN payment_method"))
