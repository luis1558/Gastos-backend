"""add goals and goal contributions

Revision ID: 8a4c2e6b1f90
Revises: 5d7f1a9c3e21
Create Date: 2026-11-02 12:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = '8a4c2e6b1f90'
down_revision = '5d7f1a9c3e21'
branch_labels = None
depends_on = None


goal_kind_enum = postgresql.ENUM('debt', 'card', 'fixed_payment', 'personal', name='goal_kind_enum', create_type=False)
goal_status_enum = postgresql.ENUM('active', 'completed', name='goal_status_enum', create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    goal_kind_enum.create(bind, checkfirst=True)
    goal_status_enum.create(bind, checkfirst=True)

    op.add_column('users', sa.Column('opening_balance', sa.Numeric(precision=14, scale=2), server_default='0', nullable=False))

    op.create_table('goals',
        sa.Column('user_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('kind', goal_kind_enum, nullable=False),
        sa.Column('status', goal_status_enum, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('target_amount', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('target_date', sa.Date(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('debt_id', sa.Uuid(as_uuid=False), nullable=True),
        sa.Column('closed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('target_amount > 0', name=op.f('ck_goals_target_amount_positive')),
        sa.ForeignKeyConstraint(['debt_id'], ['debts.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_goals_user_status', 'goals', ['user_id', 'status'], unique=False)
    op.create_index(op.f('ix_goals_user_id'), 'goals', ['user_id'], unique=False)
    op.create_index(op.f('ix_goals_debt_id'), 'goals', ['debt_id'], unique=False)

    op.create_table('goal_contributions',
        sa.Column('user_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('goal_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('contribution_date', sa.Date(), nullable=False),
        sa.Column('amount', sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column('notes', sa.String(length=255), nullable=True),
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.CheckConstraint('amount <> 0', name=op.f('ck_goal_contributions_amount_non_zero')),
        sa.ForeignKeyConstraint(['goal_id'], ['goals.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_goal_contributions_goal_date', 'goal_contributions', ['goal_id', 'contribution_date'], unique=False)
    op.create_index(op.f('ix_goal_contributions_user_id'), 'goal_contributions', ['user_id'], unique=False)
    op.create_index(op.f('ix_goal_contributions_goal_id'), 'goal_contributions', ['goal_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_goal_contributions_goal_id'), table_name='goal_contributions')
    op.drop_index(op.f('ix_goal_contributions_user_id'), table_name='goal_contributions')
    op.drop_index('ix_goal_contributions_goal_date', table_name='goal_contributions')
    op.drop_table('goal_contributions')

    op.drop_index(op.f('ix_goals_debt_id'), table_name='goals')
    op.drop_index(op.f('ix_goals_user_id'), table_name='goals')
    op.drop_index('ix_goals_user_status', table_name='goals')
    op.drop_table('goals')

    op.drop_column('users', 'opening_balance')

    op.execute('DROP TYPE IF EXISTS goal_status_enum')
    op.execute('DROP TYPE IF EXISTS goal_kind_enum')
