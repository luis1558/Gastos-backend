"""add cards, card statements and link goals to cards

Revision ID: e5b1a8d4f362
Revises: c3d9f1a7e520
Create Date: 2026-11-02 21:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e5b1a8d4f362'
down_revision = 'c3d9f1a7e520'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('cards',
        sa.Column('user_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('category_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('name', sa.String(length=120), nullable=False),
        sa.Column('last_four', sa.String(length=4), nullable=True),
        sa.Column('payment_day', sa.SmallInteger(), nullable=False),
        sa.Column('tracks_purchases', sa.Boolean(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('payment_day BETWEEN 1 AND 31', name=op.f('ck_cards_valid_payment_day')),
        sa.ForeignKeyConstraint(['category_id'], ['expense_categories.id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_cards_user_active', 'cards', ['user_id', 'is_active'], unique=False)
    op.create_index(op.f('ix_cards_user_id'), 'cards', ['user_id'], unique=False)

    op.create_table('card_statements',
        sa.Column('user_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('card_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('year', sa.SmallInteger(), nullable=False),
        sa.Column('month', sa.SmallInteger(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('paid_on', sa.Date(), nullable=True),
        sa.Column('expense_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('amount > 0', name=op.f('ck_card_statements_amount_positive')),
        sa.CheckConstraint('month BETWEEN 1 AND 12', name=op.f('ck_card_statements_valid_month')),
        sa.ForeignKeyConstraint(['card_id'], ['cards.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['expense_id'], ['expenses.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_card_statements_period', 'card_statements', ['card_id', 'year', 'month'], unique=True)
    op.create_index(op.f('ix_card_statements_user_id'), 'card_statements', ['user_id'], unique=False)
    op.create_index(op.f('ix_card_statements_card_id'), 'card_statements', ['card_id'], unique=False)

    op.add_column('goals', sa.Column('card_id', sa.Uuid(as_uuid=False), nullable=True))
    op.create_foreign_key(op.f('fk_goals_card_id_cards'), 'goals', 'cards', ['card_id'], ['id'], ondelete='SET NULL')
    op.create_index(op.f('ix_goals_card_id'), 'goals', ['card_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_goals_card_id'), table_name='goals')
    op.drop_constraint(op.f('fk_goals_card_id_cards'), 'goals', type_='foreignkey')
    op.drop_column('goals', 'card_id')

    op.drop_index(op.f('ix_card_statements_card_id'), table_name='card_statements')
    op.drop_index(op.f('ix_card_statements_user_id'), table_name='card_statements')
    op.drop_index('ix_card_statements_period', table_name='card_statements')
    op.drop_table('card_statements')

    op.drop_index(op.f('ix_cards_user_id'), table_name='cards')
    op.drop_index('ix_cards_user_active', table_name='cards')
    op.drop_table('cards')
