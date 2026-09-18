"""Database schema + engine.

Provider-neutral: everything speaks `DATABASE_URL`. Local dev defaults to a
SQLite file; production points at managed Postgres (Neon) via the same env var —
no code change, just the connection string.
"""

from __future__ import annotations

import os

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    func,
)
from sqlalchemy.engine import Engine

DEFAULT_URL = "sqlite:///worker.db"


def database_url() -> str:
    # Managed Postgres (e.g. Neon) hands us a postgres:// URL; normalise it to
    # the psycopg3 driver SQLAlchemy expects.
    url = os.environ.get("DATABASE_URL", DEFAULT_URL)
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+psycopg://", 1)
    elif url.startswith("postgresql://"):
        url = url.replace("postgresql://", "postgresql+psycopg://", 1)
    return url


metadata = MetaData()

# One row per distinct artifact, keyed by content hash so re-ingesting the same
# skill is idempotent.
artifacts = Table(
    "artifacts",
    metadata,
    Column("hash", String(64), primary_key=True),
    Column("source", String(32), nullable=False),
    Column("source_url", Text),
    Column("identity", String(256)),
    Column("kind", String(32)),
    Column("repo", String(256)),  # owner/repo (GitHub sources)
    Column("path", Text),  # path of the SKILL.md inside the repo
    Column("name", String(256)),  # frontmatter `name`
    Column("description", Text),  # frontmatter `description`
    Column("content", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), server_default=func.now()),
)

# The work queue. status: pending -> running -> done | error.
jobs = Table(
    "jobs",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("artifact_hash", String(64), nullable=False, index=True),
    Column("status", String(16), nullable=False, default="pending", index=True),
    Column("attempts", Integer, nullable=False, default=0),
    Column("error", Text),
    Column("locked_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), server_default=func.now()),
    Column("updated_at", DateTime(timezone=True), server_default=func.now()),
)

# One scored result per artifact (latest wins).
results = Table(
    "results",
    metadata,
    Column("artifact_hash", String(64), primary_key=True),
    Column("risk", Float, nullable=False),
    Column("decision", String(16), nullable=False, index=True),
    Column("mean_confidence", Float),
    Column("integrity_warning", Text),
    Column("families", JSON),
    Column("signals", JSON),
    # Every question's raw reading {id: {"v": value, "c": confidence}}, so weights
    # and thresholds can be re-tuned offline with no Jev call.
    Column("readings", JSON),
    Column("model", String(64)),
    Column("input_tokens", Integer),
    Column("cost_usd", Float),
    Column("weights_version", Integer),
    Column("scored_at", DateTime(timezone=True), server_default=func.now()),
)


def get_engine() -> Engine:
    url = database_url()
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, pool_pre_ping=True, connect_args=connect_args)


# Read-path indexes for the hub (Postgres only): the keyset order used by the
# paginated catalog, and trigram indexes so ILIKE search stays fast at scale.
_PG_INDEXES = (
    "CREATE EXTENSION IF NOT EXISTS pg_trgm",
    "CREATE INDEX IF NOT EXISTS results_risk_hash_idx "
    "ON results (risk DESC, artifact_hash DESC)",
    "CREATE INDEX IF NOT EXISTS artifacts_identity_trgm_idx "
    "ON artifacts USING gin (identity gin_trgm_ops)",
    "CREATE INDEX IF NOT EXISTS artifacts_source_url_trgm_idx "
    "ON artifacts USING gin (source_url gin_trgm_ops)",
    "CREATE INDEX IF NOT EXISTS artifacts_name_trgm_idx "
    "ON artifacts USING gin (name gin_trgm_ops)",
    "CREATE INDEX IF NOT EXISTS artifacts_description_trgm_idx "
    "ON artifacts USING gin (description gin_trgm_ops)",
)


def _add_missing_columns(engine: Engine) -> None:
    """create_all never alters existing tables; add columns introduced later."""
    from sqlalchemy import inspect

    insp = inspect(engine)
    with engine.begin() as conn:
        for table in (artifacts, results):
            have = {c["name"] for c in insp.get_columns(table.name)}
            for col in table.columns:
                if col.name not in have:
                    conn.exec_driver_sql(
                        f"ALTER TABLE {table.name} ADD COLUMN {col.name} "
                        f"{col.type.compile(engine.dialect)}")


def init_db(engine: Engine) -> None:
    metadata.create_all(engine)
    _add_missing_columns(engine)
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            for stmt in _PG_INDEXES:
                conn.exec_driver_sql(stmt)
