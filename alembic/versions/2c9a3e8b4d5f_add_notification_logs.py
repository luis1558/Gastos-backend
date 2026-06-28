"""add notification logs

Revision ID: 2c9a3e8b4d5f
Revises: 0bbf40f2c677
Create Date: 2026-06-27 08:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision = '2c9a3e8b4d5f'
down_revision = '0bbf40f2c677'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('notification_logs',
        sa.Column('debt_id', sa.Uuid(as_uuid=False), nullable=False),
        sa.Column('reminder_type', sa.Enum('seven_days', 'three_days', 'due_date', name='reminder_type_enum', values_callable=lambda x: [e.value for e in x]), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('id', sa.Uuid(as_uuid=False), nullable=False),
        sa.ForeignKeyConstraint(['debt_id'], ['debts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_notification_logs_debt_reminder', 'notification_logs', ['debt_id', 'reminder_type'], unique=True)
    op.create_index(op.f('ix_notification_logs_debt_id'), 'notification_logs', ['debt_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_notification_logs_debt_id'), table_name='notification_logs')
    op.drop_index('ix_notification_logs_debt_reminder', table_name='notification_logs')
    op.drop_table('notification_logs')
    op.execute('DROP TYPE IF EXISTS reminder_type_enum')
