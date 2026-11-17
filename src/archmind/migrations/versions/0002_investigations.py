"""Durable, immutable edge-bound investigation contexts and conversation turns."""

from alembic import op

revision = "0002_investigations"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE investigations (
      id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
      snapshot_id TEXT NOT NULL REFERENCES snapshots(id), edge_id TEXT NOT NULL,
      source_id TEXT NOT NULL, target_id TEXT NOT NULL, relationship TEXT NOT NULL,
      created_at TEXT NOT NULL,
      FOREIGN KEY(snapshot_id,edge_id) REFERENCES edges(snapshot_id,id),
      FOREIGN KEY(snapshot_id,source_id) REFERENCES nodes(snapshot_id,id),
      FOREIGN KEY(snapshot_id,target_id) REFERENCES nodes(snapshot_id,id)
    )""")
    op.execute("""CREATE TABLE investigation_turns (
      id TEXT PRIMARY KEY, investigation_id TEXT NOT NULL REFERENCES investigations(id),
      role TEXT NOT NULL CHECK(role IN ('user','assistant')),
      content_json TEXT NOT NULL, created_at TEXT NOT NULL
    )""")
    op.execute(
        "CREATE INDEX idx_investigation_turns ON investigation_turns(investigation_id,created_at,id)"
    )


def downgrade():
    op.execute("DROP TABLE investigation_turns")
    op.execute("DROP TABLE investigations")
