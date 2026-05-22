from collections.abc import Iterator
import logging

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from its.event_log.config import get_event_log_settings
from its.event_log.models import EventLogBase

logger = logging.getLogger(__name__)

_engine = None
_session_factory: sessionmaker[Session] | None = None


def get_event_log_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(
            get_event_log_settings().database_url,
            pool_pre_ping=True,
        )
    return _engine


def get_event_log_session_factory() -> sessionmaker[Session]:
    global _session_factory
    if _session_factory is None:
        _session_factory = sessionmaker(
            bind=get_event_log_engine(),
            autoflush=False,
            autocommit=False,
        )
    return _session_factory


def get_event_log_session() -> Iterator[Session]:
    with get_event_log_session_factory()() as session:
        yield session


def ensure_event_log_schema() -> None:
    try:
        engine = get_event_log_engine()
        with engine.begin() as connection:
            connection.execute(text("SELECT pg_advisory_lock(27052201)"))
            try:
                EventLogBase.metadata.create_all(bind=connection)
                _ensure_event_log_columns(connection)
                _ensure_append_only_triggers(connection)
            finally:
                connection.execute(text("SELECT pg_advisory_unlock(27052201)"))
    except SQLAlchemyError:
        logger.exception("Could not initialize event log schema")


def _ensure_event_log_columns(connection) -> None:
    connection.execute(
        text(
            """
            ALTER TABLE event_logs
            ADD COLUMN IF NOT EXISTS ip_address VARCHAR(128) NOT NULL DEFAULT 'unknown'
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE INDEX IF NOT EXISTS ix_event_logs_ip_address
            ON event_logs (ip_address)
            """
        )
    )


def _ensure_append_only_triggers(connection) -> None:
    connection.execute(
        text(
            """
            CREATE OR REPLACE FUNCTION prevent_event_logs_mutation()
            RETURNS trigger AS $$
            BEGIN
                RAISE EXCEPTION 'event_logs is append-only: % is not allowed', TG_OP;
            END;
            $$ LANGUAGE plpgsql
            """
        )
    )
    connection.execute(
        text(
            """
            DROP TRIGGER IF EXISTS event_logs_prevent_update ON event_logs
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE TRIGGER event_logs_prevent_update
            BEFORE UPDATE ON event_logs
            FOR EACH ROW EXECUTE FUNCTION prevent_event_logs_mutation()
            """
        )
    )
    connection.execute(
        text(
            """
            DROP TRIGGER IF EXISTS event_logs_prevent_delete ON event_logs
            """
        )
    )
    connection.execute(
        text(
            """
            CREATE TRIGGER event_logs_prevent_delete
            BEFORE DELETE ON event_logs
            FOR EACH ROW EXECUTE FUNCTION prevent_event_logs_mutation()
            """
        )
    )
