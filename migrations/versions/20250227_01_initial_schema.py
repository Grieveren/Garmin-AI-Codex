"""Initial training optimizer schema."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20250227_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "daily_metrics",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("date", sa.Date(), nullable=False, unique=True),
        sa.Column("resting_hr", sa.Integer(), nullable=True),
        sa.Column("max_hr", sa.Integer(), nullable=True),
        sa.Column("hrv_morning", sa.Integer(), nullable=True),
        sa.Column("sleep_seconds", sa.Integer(), nullable=True),
        sa.Column("sleep_score", sa.Integer(), nullable=True),
        sa.Column("deep_sleep_seconds", sa.Integer(), nullable=True),
        sa.Column("light_sleep_seconds", sa.Integer(), nullable=True),
        sa.Column("rem_sleep_seconds", sa.Integer(), nullable=True),
        sa.Column("steps", sa.Integer(), nullable=True),
        sa.Column("distance_meters", sa.Integer(), nullable=True),
        sa.Column("active_calories", sa.Integer(), nullable=True),
        sa.Column("stress_avg", sa.Integer(), nullable=True),
        sa.Column("body_battery_charged", sa.Integer(), nullable=True),
        sa.Column("body_battery_drained", sa.Integer(), nullable=True),
        sa.Column("body_battery_max", sa.Integer(), nullable=True),
        sa.Column("training_readiness_score", sa.Integer(), nullable=True),
        sa.Column("vo2_max", sa.Float(), nullable=True),
        sa.Column("training_status", sa.String(length=50), nullable=True),
        sa.Column("spo2_avg", sa.Float(), nullable=True),
        sa.Column("spo2_min", sa.Float(), nullable=True),
        sa.Column("respiration_avg", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_daily_metrics_date",
        "daily_metrics",
        ["date"],
        unique=False,
    )

    op.create_table(
        "activities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("activity_type", sa.String(length=50), nullable=True),
        sa.Column("activity_name", sa.String(length=200), nullable=True),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("distance_meters", sa.Float(), nullable=True),
        sa.Column("aerobic_training_effect", sa.Float(), nullable=True),
        sa.Column("anaerobic_training_effect", sa.Float(), nullable=True),
        sa.Column("training_load", sa.Integer(), nullable=True),
        sa.Column("avg_hr", sa.Integer(), nullable=True),
        sa.Column("max_hr", sa.Integer(), nullable=True),
        sa.Column("avg_pace", sa.Float(), nullable=True),
        sa.Column("elevation_gain", sa.Float(), nullable=True),
        sa.Column("calories", sa.Integer(), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=False), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_activities_date",
        "activities",
        ["date"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_activities_date", table_name="activities")
    op.drop_table("activities")
    op.drop_index("ix_daily_metrics_date", table_name="daily_metrics")
    op.drop_table("daily_metrics")
