"""link expenses to the card used for the purchase

Revision ID: f7a2c9e1b480
Revises: e5b1a8d4f362
Create Date: 2026-11-02 23:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f7a2c9e1b480'
down_revision = 'e5b1a8d4f362'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('expenses', sa.Column('card_id', sa.Uuid(as_uuid=False), nullable=True))
    op.create_foreign_key(op.f('fk_expenses_card_id_cards'), 'expenses', 'cards', ['card_id'], ['id'], ondelete='SET NULL')
    op.create_index(op.f('ix_expenses_card_id'), 'expenses', ['card_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_expenses_card_id'), table_name='expenses')
    op.drop_constraint(op.f('fk_expenses_card_id_cards'), 'expenses', type_='foreignkey')
    op.drop_column('expenses', 'card_id')
