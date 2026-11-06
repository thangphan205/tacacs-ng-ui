"""alertevent.channel_id: nullable, ON DELETE SET NULL

Revision ID: f3a8c1d5e927
Revises: e7f2c4a8b153
Create Date: 2026-11-06 00:00:00.000000

An alert that fired with no notification channel left no event, and deleting
a channel deleted every event delivered through it (#357). Events now outlive
their channel, and a rule firing without channels is recorded with no channel.

Existing rows are untouched.

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "f3a8c1d5e927"
down_revision = "e7f2c4a8b153"
branch_labels = None
depends_on = None

_FK = "alertevent_channel_id_fkey"


def upgrade():
    op.alter_column("alertevent", "channel_id", nullable=True)
    op.drop_constraint(_FK, "alertevent", type_="foreignkey")
    op.create_foreign_key(
        _FK,
        "alertevent",
        "notificationchannel",
        ["channel_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade():
    # Events without a channel cannot satisfy NOT NULL again.
    op.execute("DELETE FROM alertevent WHERE channel_id IS NULL")
    op.drop_constraint(_FK, "alertevent", type_="foreignkey")
    op.create_foreign_key(
        _FK,
        "alertevent",
        "notificationchannel",
        ["channel_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.alter_column("alertevent", "channel_id", nullable=False)
