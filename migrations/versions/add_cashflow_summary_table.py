"""جدول cashflow_summary لتقرير التدفق النقدي — إن وُجد يُستخدم من الواجهة؛ إن لم يُنشأ يبقى التقرير يعتمد على قيود اليومية.

Revision ID: cashflow_01
Revises: cust_cols_01
Create Date: 2026-02-03

البنية المتوقعة: account_code, account_name, line_date (أو date), debit, credit
"""
from alembic import op
from sqlalchemy import text


revision = 'cashflow_01'
down_revision = 'cust_cols_01'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()
    dialect = conn.dialect.name
    if dialect == 'postgresql':
        op.execute(text("""
            CREATE TABLE IF NOT EXISTS cashflow_summary (
                id SERIAL PRIMARY KEY,
                account_code VARCHAR(20) NOT NULL,
                account_name VARCHAR(200),
                line_date DATE NOT NULL,
                debit NUMERIC(18,2) DEFAULT 0,
                credit NUMERIC(18,2) DEFAULT 0
            )
        """))
        op.execute(text("CREATE INDEX IF NOT EXISTS ix_cashflow_summary_line_date ON cashflow_summary (line_date)"))
    else:
        try:
            op.execute(text("""
                CREATE TABLE IF NOT EXISTS cashflow_summary (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    account_code VARCHAR(20) NOT NULL,
                    account_name VARCHAR(200),
                    line_date DATE NOT NULL,
                    debit NUMERIC(18,2) DEFAULT 0,
                    credit NUMERIC(18,2) DEFAULT 0
                )
            """))
            op.execute(text("CREATE INDEX IF NOT EXISTS ix_cashflow_summary_line_date ON cashflow_summary (line_date)"))
        except Exception:
            pass


def downgrade():
    op.execute(text("DROP TABLE IF EXISTS cashflow_summary"))
