"""Initial migration

Revision ID: b4fe997e5c15
Revises: 
Create Date: 2025-09-20 16:45:13.552064

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


# revision identifiers, used by Alembic.
revision = 'b4fe997e5c15'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Table name must be 'users' to match models.User __tablename__.
    # Create only if missing (app may have run db.create_all() on load).
    conn = op.get_bind()
    insp = inspect(conn)
    if not insp.has_table('users') and not insp.has_table('user'):
        op.create_table('users',
            sa.Column('id', sa.Integer(), nullable=False),
            sa.Column('username', sa.String(length=150), nullable=False),
            sa.Column('password_hash', sa.String(length=128), nullable=False),
            sa.PrimaryKeyConstraint('id'),
            sa.UniqueConstraint('username')
        )
    elif insp.has_table('user') and not insp.has_table('users'):
        # Legacy DB had table 'user'; rename to 'users' to match model.
        op.execute(sa.text('ALTER TABLE user RENAME TO users'))


def downgrade():
    conn = op.get_bind()
    insp = inspect(conn)
    if insp.has_table('users'):
        op.drop_table('users')
