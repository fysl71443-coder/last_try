"""Add account usage (usage_group, is_control, allow_posting) and account_usage_map table

Revision ID: acc_usage_01
Revises: d79c61656053
Create Date: 2026-02-02

"""
from alembic import op
from sqlalchemy import text, Column, Integer, String, Boolean, ForeignKey


revision = 'acc_usage_01'
down_revision = 'd79c61656053'
branch_labels = None
depends_on = None


def upgrade():
    for col, typ in [
        ('usage_group', 'VARCHAR(30)'),
        ('is_control', 'INTEGER'),
        ('allow_posting', 'INTEGER'),
    ]:
        try:
            op.execute(text(f"ALTER TABLE accounts ADD COLUMN {col} {typ}"))
        except Exception:
            pass

    op.execute(text("""
        CREATE TABLE IF NOT EXISTS account_usage_map (
            id INTEGER NOT NULL PRIMARY KEY,
            module VARCHAR(50) NOT NULL,
            action VARCHAR(50) NOT NULL,
            usage_group VARCHAR(30) NOT NULL,
            account_id INTEGER NOT NULL,
            is_default INTEGER,
            active INTEGER,
            FOREIGN KEY(account_id) REFERENCES accounts (id)
        )
    """))
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_account_usage_map_module ON account_usage_map (module)"))
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_account_usage_map_action ON account_usage_map (action)"))
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_account_usage_map_usage_group ON account_usage_map (usage_group)"))
    op.execute(text("CREATE INDEX IF NOT EXISTS ix_account_usage_map_account_id ON account_usage_map (account_id)"))


def downgrade():
    op.execute(text("DROP TABLE IF EXISTS account_usage_map"))
    # Optional: drop columns from accounts (SQLite 3.35.0+ supports DROP COLUMN)
    pass
