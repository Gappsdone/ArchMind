"""Alembic environment for ArchMind's SQLite schema."""

from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.engine import URL

path = context.config.get_main_option("archmind_db_path")
engine = create_engine(URL.create("sqlite", database=path))
with engine.connect() as connection:
    connection.exec_driver_sql("PRAGMA foreign_keys=ON")
    context.configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()
    connection.commit()
