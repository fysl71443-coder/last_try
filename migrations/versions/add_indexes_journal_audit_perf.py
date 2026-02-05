"""فهارس إضافية لتسريع استعلامات القيود والتدقيق

Revision ID: idx_journal_audit_01
Revises: audit_snap_01
Create Date: 2026-02-04

"""
from alembic import op
from sqlalchemy import text


revision = 'idx_journal_audit_01'
down_revision = 'audit_snap_01'
branch_labels = None
depends_on = None


def upgrade():
    # journal_lines.journal_id — استعلامات القيود مع الأسطر
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_journal_lines_journal_id ON journal_lines (journal_id)"))
    # journal_entries.date — قوائم وفلترة بالتاريخ
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_journal_entries_date ON journal_entries (date)"))
    # audit_snapshots — آخر لقطة حسب السنة
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_audit_snapshots_fy_run ON audit_snapshots (fiscal_year_id, run_at)"))


def downgrade():
    op.execute(text("DROP INDEX IF EXISTS ix_audit_snapshots_fy_run"))
    op.execute(text("DROP INDEX IF EXISTS ix_journal_entries_date"))
    op.execute(text("DROP INDEX IF EXISTS ix_journal_lines_journal_id"))
