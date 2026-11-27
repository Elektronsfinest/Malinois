"""add_user_roles_and_supervisor

Revision ID: 978f35d26175
Revises: 110e34ca41c8
Create Date: 2026-11-24 16:17:24.457465

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '978f35d26175'
down_revision: Union[str, Sequence[str], None] = '110e34ca41c8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('role', sa.String(length=20), server_default='user', nullable=False)
        )
        batch_op.add_column(sa.Column('supervisor_id', sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column(
                'must_change_password',
                sa.Boolean(),
                server_default=sa.false(),
                nullable=False,
            )
        )
        batch_op.create_index(
            batch_op.f('ix_users_supervisor_id'), ['supervisor_id'], unique=False
        )
        batch_op.create_foreign_key(
            'fk_users_supervisor_id_users', 'users', ['supervisor_id'], ['id']
        )


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint('fk_users_supervisor_id_users', type_='foreignkey')
        batch_op.drop_index(batch_op.f('ix_users_supervisor_id'))
        batch_op.drop_column('must_change_password')
        batch_op.drop_column('supervisor_id')
        batch_op.drop_column('role')
