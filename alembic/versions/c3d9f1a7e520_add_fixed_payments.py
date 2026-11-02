"""add fixed payments and link goals to them

Revision ID: c3d9f1a7e520
Revises: 8a4c2e6b1f90
Create Date: 2026-11-02 18:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3d9f1a7e520'
down_revision = '8a4c2e6b1f90'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('fixed_payments',
        sa.Column('user_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('category_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('day_of_month', sa.SmallInteger(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('amount > 0', name=op.f('ck_fixed_payments_amount_positive')),
        sa.CheckConstraint('day_of_month BETWEEN 1 AND 31', name=op.f('ck_fixed_payments_valid_day_of_month')),
        sa.ForeignKeyConstraint(['category_id'], ['expense_categories.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_fixed_payments_user_active', 'fixed_payments', ['user_id', 'is_active'], unique=False)
    op.create_index(op.f('ix_fixed_payments_user_id'), 'fixed_payments', ['user_id'], unique=False)

    op.create_table('fixed_payment_payments',
        sa.Column('user_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('fixed_payment_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('year', sa.SmallInteger(), nullable=False),
        sa.Column('month', sa.SmallInteger(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('paid_on', sa.Date(), nullable=False),
        sa.Column('expense_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('amount > 0', name=op.f('ck_fixed_payment_payments_amount_positive')),
        sa.CheckConstraint('month BETWEEN 1 AND 12', name=op.f('ck_fixed_payment_payments_valid_month')),
        sa.ForeignKeyConstraint(['expense_id'], ['expenses.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['fixed_payment_id'], ['fixed_payments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_fixed_payment_payments_period', 'fixed_payment_payments', ['fixed_payment_id', 'year', 'month'], unique=True)
    op.create_index(op.f('ix_fixed_payment_payments_user_id'), 'fixed_payment_payments', ['user_id'], unique=False)
    op.create_index(op.f('ix_fixed_payment_payments_fixed_payment_id'), 'fixed_payment_payments', ['fixed_payment_id'], unique=False)

    op.add_column('goals', sa.Column('fixed_payment_id', sa.Uuid(as_uuid=False), nullable=True))
    op.create_foreign_key(op.f('fk_goals_fixed_payment_id_fixed_payments'), 'goals', 'fixed_payments', ['fixed_payment_id'], ['id'], ondelete='SET NULL')
    op.create_index(op.f('ix_goals_fixed_payment_id'), 'goals', ['fixed_payment_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_goals_fixed_payment_id'), table_name='goals')
    op.drop_constraint(op.f('fk_goals_fixed_payment_id_fixed_payments'), 'goals', type_='foreignkey')
    op.drop_column('goals', 'fixed_payment_id')

    op.drop_index(op.f('ix_fixed_payment_payments_fixed_payment_id'), table_name='fixed_payment_payments')
    op.drop_index(op.f('ix_fixed_payment_payments_user_id'), table_name='fixed_payment_payments')
    op.drop_index('ix_fixed_payment_payments_period', table_name='fixed_payment_payments')
    op.drop_table('fixed_payment_payments')

    op.drop_index(op.f('ix_fixed_payments_user_id'), table_name='fixed_payments')
    op.drop_index('ix_fixed_payments_user_active', table_name='fixed_payments')
    op.drop_table('fixed_payments')
