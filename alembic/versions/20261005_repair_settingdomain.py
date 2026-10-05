"""Repair missing settings domains, including the hiring seed's operations marker.

Revision ID: 20261005_settingdomain_repair
Revises: 20260616_add_collaboration
Create Date: 2026-10-05
"""

from alembic import op

revision = "20261005_settingdomain_repair"
down_revision = "20260616_add_collaboration"
branch_labels = None
depends_on = None

# Frozen snapshot of the application's persisted SettingDomain names.
SETTING_DOMAINS = (
    "auth",
    "audit",
    "scheduler",
    "automation",
    "email",
    "features",
    "reporting",
    "payments",
    "operations",
    "support",
    "inventory",
    "projects",
    "fleet",
    "procurement",
    "settings",
    "payroll",
    "banking",
    "coach",
    "notifications",
    "expense",
    "gl",
)


def upgrade() -> None:
    # Commit enum additions before later migrations or startup queries use them.
    with op.get_context().autocommit_block():
        for domain in SETTING_DOMAINS:
            op.execute(f"ALTER TYPE settingdomain ADD VALUE IF NOT EXISTS '{domain}'")


def downgrade() -> None:
    # Removing enum values requires rewriting dependent data; retain the values.
    pass
