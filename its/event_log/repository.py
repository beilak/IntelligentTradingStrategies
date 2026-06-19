from dataclasses import dataclass
from datetime import datetime
import logging

from sqlalchemy import Text, cast, desc, func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from its.event_log.models import EventLogEntry
from its.event_log.storage import get_event_log_session_factory
from its.observability.metrics import (
    now_seconds,
    observe_audit_event,
    observe_audit_write,
    observe_audit_write_failure,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EventLogCreate:
    service: str
    user: str
    http_action: str
    ip_address: str
    path: str
    header: dict[str, str]
    body: str | None


@dataclass(frozen=True)
class EventLogFilters:
    id: int | None = None
    date_time_from: datetime | None = None
    date_time_to: datetime | None = None
    service: str | None = None
    user: str | None = None
    http_action: str | None = None
    ip_address: str | None = None
    path: str | None = None
    header: str | None = None
    body: str | None = None


def append_event_log(payload: EventLogCreate) -> None:
    started = now_seconds()
    try:
        with get_event_log_session_factory()() as session:
            session.add(
                EventLogEntry(
                    service=payload.service,
                    user=payload.user or "unauth",
                    http_action=payload.http_action,
                    ip_address=payload.ip_address or "unknown",
                    path=payload.path,
                    header=payload.header,
                    body=payload.body,
                )
            )
            session.commit()
        observe_audit_event(
            service=payload.service,
            method=payload.http_action,
            result="success",
        )
        observe_audit_write(
            service=payload.service,
            result="success",
            duration_seconds=now_seconds() - started,
        )
    except SQLAlchemyError as error:
        observe_audit_event(
            service=payload.service,
            method=payload.http_action,
            result="failure",
        )
        observe_audit_write(
            service=payload.service,
            result="failure",
            duration_seconds=now_seconds() - started,
        )
        observe_audit_write_failure(
            service=payload.service,
            error_type=type(error).__name__,
        )
        logger.exception("Could not append event log")


def list_event_logs(
    session: Session,
    filters: EventLogFilters,
    *,
    limit: int,
    offset: int,
) -> tuple[list[EventLogEntry], int]:
    stmt = _apply_filters(select(EventLogEntry), filters)
    count_stmt = _apply_filters(select(func.count()).select_from(EventLogEntry), filters)
    total = session.scalar(count_stmt) or 0
    items = list(
        session.scalars(
            _order_event_logs_newest_first(stmt).offset(offset).limit(limit)
        )
    )
    return items, total


def list_event_log_filter_options(session: Session) -> tuple[list[str], list[str]]:
    services = list(
        session.scalars(
            select(EventLogEntry.service)
            .distinct()
            .where(EventLogEntry.service != "")
            .order_by(EventLogEntry.service)
        )
    )
    users = list(
        session.scalars(
            select(EventLogEntry.user)
            .distinct()
            .where(EventLogEntry.user != "")
            .order_by(EventLogEntry.user)
        )
    )
    return services, users


def _apply_filters(statement, filters: EventLogFilters):
    if filters.id is not None:
        statement = statement.where(EventLogEntry.id == filters.id)
    if filters.date_time_from is not None:
        statement = statement.where(EventLogEntry.date_time >= filters.date_time_from)
    if filters.date_time_to is not None:
        statement = statement.where(EventLogEntry.date_time <= filters.date_time_to)
    if filters.service:
        statement = statement.where(EventLogEntry.service == filters.service)
    if filters.user:
        statement = statement.where(EventLogEntry.user == filters.user)
    if filters.http_action:
        statement = statement.where(EventLogEntry.http_action.ilike(_contains(filters.http_action)))
    if filters.ip_address:
        statement = statement.where(EventLogEntry.ip_address.ilike(_contains(filters.ip_address)))
    if filters.path:
        statement = statement.where(EventLogEntry.path.ilike(_contains(filters.path)))
    if filters.header:
        statement = statement.where(cast(EventLogEntry.header, Text).ilike(_contains(filters.header)))
    if filters.body:
        statement = statement.where(EventLogEntry.body.ilike(_contains(filters.body)))
    return statement


def _order_event_logs_newest_first(statement):
    return statement.order_by(desc(EventLogEntry.date_time), desc(EventLogEntry.id))


def _contains(value: str) -> str:
    return f"%{value.strip()}%"
