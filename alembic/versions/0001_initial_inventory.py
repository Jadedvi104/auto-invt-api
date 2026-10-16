"""Create hosts, agents, and task definitions with relational constraints.

Revision ID: 0001_initial_inventory
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0001_initial_inventory"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def record_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "hosts",
        *record_columns(),
        sa.Column("hostname", sa.String(253), nullable=False),
        sa.Column("environment", sa.String(64), server_default="dev", nullable=False),
        sa.Column("status", sa.String(16), server_default="active", nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_hosts"),
        sa.UniqueConstraint("hostname", name="uq_hosts_hostname"),
        sa.CheckConstraint("status IN ('active', 'inactive', 'maintenance')", name="valid_status"),
        sa.CheckConstraint("version >= 1", name="positive_version"),
    )
    op.create_index("ix_hosts_created_at_id", "hosts", ["created_at", "id"])
    op.create_index("ix_hosts_status", "hosts", ["status"])
    op.create_index("ix_hosts_environment", "hosts", ["environment"])
    op.create_table(
        "agents",
        *record_columns(),
        sa.Column("host_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("state", sa.String(16), server_default="offline", nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_agents"),
        sa.ForeignKeyConstraint(
            ["host_id"], ["hosts.id"], name="fk_agents_host_id_hosts", ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("host_id", "name", name="uq_agents_host_id_name"),
        sa.CheckConstraint("state IN ('online', 'offline', 'disabled')", name="valid_state"),
        sa.CheckConstraint("version >= 1", name="positive_version"),
    )
    op.create_index("ix_agents_host_id", "agents", ["host_id"])
    op.create_index("ix_agents_created_at_id", "agents", ["created_at", "id"])
    op.create_index("ix_agents_state", "agents", ["state"])
    op.create_table(
        "task_definitions",
        *record_columns(),
        sa.Column("agent_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column(
            "command_template_metadata", sa.JSON(), server_default=sa.text("'{}'"), nullable=False
        ),
        sa.Column("enabled", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_task_definitions"),
        sa.ForeignKeyConstraint(
            ["agent_id"],
            ["agents.id"],
            name="fk_task_definitions_agent_id_agents",
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("version >= 1", name="positive_version"),
    )
    op.create_index("ix_task_definitions_agent_id", "task_definitions", ["agent_id"])
    op.create_index("ix_task_definitions_created_at_id", "task_definitions", ["created_at", "id"])
    op.create_index("ix_task_definitions_enabled", "task_definitions", ["enabled"])


def downgrade() -> None:
    op.drop_index("ix_task_definitions_enabled", table_name="task_definitions")
    op.drop_index("ix_task_definitions_created_at_id", table_name="task_definitions")
    op.drop_index("ix_task_definitions_agent_id", table_name="task_definitions")
    op.drop_table("task_definitions")
    op.drop_index("ix_agents_state", table_name="agents")
    op.drop_index("ix_agents_created_at_id", table_name="agents")
    op.drop_index("ix_agents_host_id", table_name="agents")
    op.drop_table("agents")
    op.drop_index("ix_hosts_environment", table_name="hosts")
    op.drop_index("ix_hosts_status", table_name="hosts")
    op.drop_index("ix_hosts_created_at_id", table_name="hosts")
    op.drop_table("hosts")
