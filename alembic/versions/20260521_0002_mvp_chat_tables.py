"""mvp chat aggregate tables

Revision ID: 20260521_0002
Revises: 20260520_0001
Create Date: 2026-05-21
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260521_0002"
down_revision: str | None = "20260520_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sessions",
        sa.Column("session_id", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("session_id"),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=255), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_session_id", "messages", ["session_id"])

    op.create_table(
        "turns",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=255), nullable=False),
        sa.Column("user_message", sa.Text(), nullable=False),
        sa.Column("assistant_message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=50), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("scenario", sa.String(length=50), nullable=True),
        sa.Column("activated_casel", sa.JSON(), nullable=False),
        sa.Column("best_candidate_id", sa.String(length=255), nullable=True),
        sa.Column("failed_module", sa.String(length=50), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=False),
        sa.Column("fallback_message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["sessions.session_id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_turns_session_id", "turns", ["session_id"])

    op.create_table(
        "candidates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("turn_id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.String(length=255), nullable=False),
        sa.Column("orientation", sa.String(length=50), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("epitome_er", sa.Integer(), nullable=False),
        sa.Column("epitome_ip", sa.Integer(), nullable=False),
        sa.Column("epitome_ex", sa.Integer(), nullable=False),
        sa.Column("casel_scores_json", sa.JSON(), nullable=False),
        sa.Column("boundary_flag", sa.Boolean(), nullable=False),
        sa.Column("boundary_reason", sa.Text(), nullable=False),
        sa.Column("weighted_total", sa.Float(), nullable=False),
        sa.Column("is_winner", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["turn_id"], ["turns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_candidates_turn_id", "candidates", ["turn_id"])
    op.create_index("ix_candidates_candidate_id", "candidates", ["candidate_id"])

    op.create_table(
        "preference_pairs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("turn_id", sa.Integer(), nullable=False),
        sa.Column("winner_id", sa.String(length=255), nullable=False),
        sa.Column("loser_id", sa.String(length=255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["turn_id"], ["turns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_preference_pairs_turn_id", "preference_pairs", ["turn_id"])
    op.create_index("ix_preference_pairs_winner_id", "preference_pairs", ["winner_id"])
    op.create_index("ix_preference_pairs_loser_id", "preference_pairs", ["loser_id"])


def downgrade() -> None:
    op.drop_index("ix_preference_pairs_loser_id", "preference_pairs")
    op.drop_index("ix_preference_pairs_winner_id", "preference_pairs")
    op.drop_index("ix_preference_pairs_turn_id", "preference_pairs")
    op.drop_table("preference_pairs")
    op.drop_index("ix_candidates_candidate_id", "candidates")
    op.drop_index("ix_candidates_turn_id", "candidates")
    op.drop_table("candidates")
    op.drop_index("ix_turns_session_id", "turns")
    op.drop_table("turns")
    op.drop_index("ix_messages_session_id", "messages")
    op.drop_table("messages")
    op.drop_table("sessions")
