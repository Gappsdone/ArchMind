"""Initial graph and job schema."""

from alembic import op

from archmind.core import SCHEMA

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    for statement in SCHEMA.split(";"):
        if statement.strip():
            op.execute(statement)


def downgrade():
    for table in ("evidence", "edges", "nodes", "jobs", "snapshots", "projects"):
        op.execute(f"DROP TABLE IF EXISTS {table}")
