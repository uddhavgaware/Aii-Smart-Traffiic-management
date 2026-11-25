"""Initial database schema migration.

Revision ID: 001_initial
Revises:
Create Date: 2026-11-25
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.Enum("admin", "operator", "viewer", name="user_role"), nullable=False, server_default="viewer"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_users_username", "users", ["username"])

    op.create_table(
        "cameras",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("unique_id", sa.String(64), nullable=False, unique=True),
        sa.Column("direction", sa.Enum("north", "south", "east", "west", name="camera_direction"), nullable=False, unique=True),
        sa.Column("status", sa.Enum("online", "offline", "connecting", "error", name="camera_status"), nullable=False, server_default="offline"),
        sa.Column("stream_url", sa.String(512), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("registered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        "traffic_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("direction", sa.String(16), nullable=False, index=True),
        sa.Column("vehicle_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("density_level", sa.String(24), nullable=False, server_default="LOW"),
        sa.Column("speed_estimate", sa.Float(), nullable=True),
        sa.Column("queue_length", sa.Float(), nullable=False, server_default="0"),
        sa.Column("congestion_predicted", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )

    op.create_table(
        "signal_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("direction", sa.String(16), nullable=False, index=True),
        sa.Column("phase", sa.String(16), nullable=False),
        sa.Column("duration", sa.Integer(), nullable=False),
        sa.Column("reason", sa.String(255), nullable=False, server_default=""),
        sa.Column("triggered_by", sa.String(24), nullable=False, server_default="auto"),
        sa.Column("mode", sa.String(16), nullable=False, server_default="AUTO"),
    )

    op.create_table(
        "emergency_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("direction", sa.String(16), nullable=False, index=True),
        sa.Column("vehicle_type", sa.String(32), nullable=False, server_default="ambulance"),
        sa.Column("stage1_detected", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("stage2_confirmed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("cleared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("signal_response", sa.String(512), nullable=True),
    )

    op.create_table(
        "system_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, index=True),
        sa.Column("event_type", sa.String(64), nullable=False, index=True),
        sa.Column("severity", sa.Enum("info", "warning", "error", "critical", name="event_severity"), nullable=False, server_default="info"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("acknowledged", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("system_events")
    op.drop_table("emergency_events")
    op.drop_table("signal_events")
    op.drop_table("traffic_events")
    op.drop_table("cameras")
    op.drop_table("users")
