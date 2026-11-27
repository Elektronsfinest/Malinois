"""add backup_logs table

Revision ID: 130c9efec21a
Revises: b984904210a3
Create Date: 2026-11-26 07:35:20.398963

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '130c9efec21a'
down_revision: Union[str, Sequence[str], None] = 'b984904210a3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'backup_logs',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(length=255), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('backup_type', sa.String(length=20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_by_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id'], name='fk_backup_logs_created_by_id'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('filename'),
    )
    with op.batch_alter_table('backup_logs', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_backup_logs_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_backup_logs_id'), ['id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('backup_logs', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_backup_logs_id'))
        batch_op.drop_index(batch_op.f('ix_backup_logs_created_at'))

    op.drop_table('backup_logs')
