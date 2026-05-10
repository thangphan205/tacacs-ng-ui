"""add alert anomaly tables

Revision ID: a1b2c3d4e5f6
Revises: ff45a8b12c03
Create Date: 2026-05-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
import sqlmodel

# revision identifiers, used by Alembic.
revision = "a1b2c3d4e5f6"
down_revision = "ff45a8b12c03"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alertrule",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sqlmodel.AutoString(length=255), nullable=False),
        sa.Column("description", sqlmodel.AutoString(length=1024), nullable=True),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("log_type", sqlmodel.AutoString(length=50), nullable=False),
        sa.Column("condition_field", sqlmodel.AutoString(length=100), nullable=False),
        sa.Column("condition_operator", sqlmodel.AutoString(length=50), nullable=False),
        sa.Column("threshold", sa.Float(), nullable=True),
        sa.Column("time_window_minutes", sa.Integer(), nullable=False),
        sa.Column("severity", sqlmodel.AutoString(length=20), nullable=False),
        sa.Column("cooldown_minutes", sa.Integer(), nullable=False),
        sa.Column("last_fired_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alertrule_name", "alertrule", ["name"], unique=False)

    op.create_table(
        "notificationchannel",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sqlmodel.AutoString(length=255), nullable=False),
        sa.Column("channel_type", sqlmodel.AutoString(length=50), nullable=False),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notificationchannel_name", "notificationchannel", ["name"], unique=False)

    op.create_table(
        "alertevent",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("rule_id", sa.Uuid(), nullable=False),
        sa.Column("channel_id", sa.Uuid(), nullable=False),
        sa.Column("triggered_at", sa.DateTime(), nullable=False),
        sa.Column("payload_snapshot", sa.Text(), nullable=True),
        sa.Column("status", sqlmodel.AutoString(length=20), nullable=False),
        sa.Column("error_message", sqlmodel.AutoString(length=1024), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["rule_id"], ["alertrule.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["channel_id"], ["notificationchannel.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_alertevent_rule_id", "alertevent", ["rule_id"], unique=False)
    op.create_index("ix_alertevent_channel_id", "alertevent", ["channel_id"], unique=False)
    op.create_index("ix_alertevent_triggered_at", "alertevent", ["triggered_at"], unique=False)

    op.create_table(
        "anomalydetectionresult",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("subject_type", sqlmodel.AutoString(length=20), nullable=False),
        sa.Column("subject_value", sqlmodel.AutoString(length=255), nullable=False),
        sa.Column("scored_at", sa.DateTime(), nullable=False),
        sa.Column("anomaly_score", sa.Float(), nullable=False),
        sa.Column("is_anomaly", sa.Boolean(), nullable=False),
        sa.Column("risk_level", sqlmodel.AutoString(length=20), nullable=False),
        sa.Column("feature_snapshot", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_anomalydetectionresult_subject_value", "anomalydetectionresult", ["subject_value"], unique=False)
    op.create_index("ix_anomalydetectionresult_scored_at", "anomalydetectionresult", ["scored_at"], unique=False)


def downgrade() -> None:
    op.drop_table("alertevent")
    op.drop_table("alertrule")
    op.drop_table("notificationchannel")
    op.drop_table("anomalydetectionresult")
