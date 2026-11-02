"""add debt interest and rate changes

Revision ID: 5d7f1a9c3e21
Revises: 2c9a3e8b4d5f
Create Date: 2026-11-02 09:30:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '5d7f1a9c3e21'
down_revision = '2c9a3e8b4d5f'
branch_labels = None
depends_on = None


interest_type_enum = postgresql.ENUM('none', 'simple', 'compound', name='interest_type_enum', create_type=False)
rate_type_enum = postgresql.ENUM('fixed', 'variable', name='rate_type_enum', create_type=False)
rate_period_enum = postgresql.ENUM('monthly', 'annual', name='rate_period_enum', create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    interest_type_enum.create(bind, checkfirst=True)
    rate_type_enum.create(bind, checkfirst=True)
    rate_period_enum.create(bind, checkfirst=True)

    op.add_column('debts', sa.Column('interest_type', interest_type_enum, server_default='none', nullable=False))
    op.add_column('debts', sa.Column('rate_type', rate_type_enum, server_default='fixed', nullable=False))
    op.add_column('debts', sa.Column('rate_period', rate_period_enum, server_default='annual', nullable=False))
    op.add_column('debts', sa.Column('interest_rate', sa.Numeric(precision=7, scale=4), server_default='0', nullable=False))
    op.create_check_constraint(op.f('ck_debts_interest_rate_non_negative'), 'debts', 'interest_rate >= 0')

    op.create_table('debt_rate_changes',
        sa.Column('user_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('debt_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('effective_date', sa.Date(), nullable=False),
        sa.Column('rate', sa.Numeric(precision=7, scale=4), nullable=False),
        sa.Column('notes', sa.String(length=255), nullable=True),
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('rate >= 0', name=op.f('ck_debt_rate_changes_rate_non_negative')),
        sa.ForeignKeyConstraint(['debt_id'], ['debts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_debt_rate_changes_debt_effective_date', 'debt_rate_changes', ['debt_id', 'effective_date'], unique=True)
    op.create_index(op.f('ix_debt_rate_changes_debt_id'), 'debt_rate_changes', ['debt_id'], unique=False)
    op.create_index(op.f('ix_debt_rate_changes_user_id'), 'debt_rate_changes', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_debt_rate_changes_user_id'), table_name='debt_rate_changes')
    op.drop_index(op.f('ix_debt_rate_changes_debt_id'), table_name='debt_rate_changes')
    op.drop_index('ix_debt_rate_changes_debt_effective_date', table_name='debt_rate_changes')
    op.drop_table('debt_rate_changes')

    op.drop_constraint(op.f('ck_debts_interest_rate_non_negative'), 'debts', type_='check')
    op.drop_column('debts', 'interest_rate')
    op.drop_column('debts', 'rate_period')
    op.drop_column('debts', 'rate_type')
    op.drop_column('debts', 'interest_type')

    op.execute('DROP TYPE IF EXISTS rate_period_enum')
    op.execute('DROP TYPE IF EXISTS rate_type_enum')
    op.execute('DROP TYPE IF EXISTS interest_type_enum')
