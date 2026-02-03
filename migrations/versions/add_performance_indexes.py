"""فهارس أداء: journal_entries، sales_invoices، purchase_invoices، payments

Revision ID: perf_idx_01
Revises: jl_line_date_idx
Create Date: 2026-02-03

"""
from alembic import op
from sqlalchemy import text


revision = 'perf_idx_01'
down_revision = 'jl_line_date_idx'
branch_labels = None
depends_on = None


def upgrade():
    # journal_entries: أغلب الاستعلامات تفلتر status + date
    op.execute(text("CREATE INDEX IF NOT EXISTS idx_journal_entries_status_date ON journal_entries (status, date)"))
    # sales_invoices: تقارير بالتاريخ والفرع
    op.execute(text("CREATE INDEX IF NOT EXISTS idx_sales_invoices_date ON sales_invoices (date)"))
    op.execute(text("CREATE INDEX IF NOT EXISTS idx_sales_invoices_branch ON sales_invoices (branch)"))
    # purchase_invoices
    op.execute(text("CREATE INDEX IF NOT EXISTS idx_purchase_invoices_date ON purchase_invoices (date)"))
    op.execute(text("CREATE INDEX IF NOT EXISTS idx_purchase_invoices_supplier ON purchase_invoices (supplier_id)"))
    # payments: تجميع المدفوعات حسب الفاتورة
    op.execute(text("CREATE INDEX IF NOT EXISTS idx_payments_invoice ON payments (invoice_type, invoice_id)"))


def downgrade():
    op.execute(text("DROP INDEX IF EXISTS idx_payments_invoice"))
    op.execute(text("DROP INDEX IF EXISTS idx_purchase_invoices_supplier"))
    op.execute(text("DROP INDEX IF EXISTS idx_purchase_invoices_date"))
    op.execute(text("DROP INDEX IF EXISTS idx_sales_invoices_branch"))
    op.execute(text("DROP INDEX IF EXISTS idx_sales_invoices_date"))
    op.execute(text("DROP INDEX IF EXISTS idx_journal_entries_status_date"))
