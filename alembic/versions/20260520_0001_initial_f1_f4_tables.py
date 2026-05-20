"""initial F1/F4 tables

Revision ID: 20260520_0001
Revises:
Create Date: 2026-05-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260520_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "safety_gate_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=255), nullable=False),
        sa.Column("risk_level", sa.String(length=20), nullable=False),
        sa.Column("matched_signals", sa.JSON(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("block_generation", sa.Boolean(), nullable=False),
        sa.Column("referral_message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_safety_gate_logs_session_id", "safety_gate_logs", ["session_id"])
    op.create_index("ix_safety_gate_logs_risk_level", "safety_gate_logs", ["risk_level"])

    op.create_table(
        "critic_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=255), nullable=False),
        sa.Column("user_message", sa.Text(), nullable=False),
        sa.Column("history", sa.JSON(), nullable=False),
        sa.Column("activated_casel", sa.JSON(), nullable=False),
        sa.Column("candidates", sa.JSON(), nullable=False),
        sa.Column("best_candidate_id", sa.String(length=255), nullable=True),
        sa.Column("preference_pair", sa.JSON(), nullable=True),
        sa.Column("fallback_message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_critic_runs_session_id", "critic_runs", ["session_id"])

    op.create_table(
        "critic_candidate_scores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("candidate_id", sa.String(length=255), nullable=False),
        sa.Column("epitome", sa.JSON(), nullable=False),
        sa.Column("casel", sa.JSON(), nullable=False),
        sa.Column("boundary_flag", sa.Boolean(), nullable=False),
        sa.Column("boundary_reason", sa.Text(), nullable=False),
        sa.Column("weighted_total", sa.Float(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["critic_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_critic_candidate_scores_run_id",
        "critic_candidate_scores",
        ["run_id"],
    )
    op.create_index(
        "ix_critic_candidate_scores_candidate_id",
        "critic_candidate_scores",
        ["candidate_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_critic_candidate_scores_candidate_id", "critic_candidate_scores")
    op.drop_index("ix_critic_candidate_scores_run_id", "critic_candidate_scores")
    op.drop_table("critic_candidate_scores")
    op.drop_index("ix_critic_runs_session_id", "critic_runs")
    op.drop_table("critic_runs")
    op.drop_index("ix_safety_gate_logs_risk_level", "safety_gate_logs")
    op.drop_index("ix_safety_gate_logs_session_id", "safety_gate_logs")
    op.drop_table("safety_gate_logs")
