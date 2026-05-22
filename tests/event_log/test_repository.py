from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from its.event_log.models import EventLogEntry
from its.event_log.repository import _order_event_logs_newest_first


def test_event_logs_are_ordered_newest_first() -> None:
    statement = _order_event_logs_newest_first(select(EventLogEntry))

    compiled = str(statement.compile(dialect=postgresql.dialect()))

    assert "ORDER BY event_logs.date_time DESC, event_logs.id DESC" in compiled
