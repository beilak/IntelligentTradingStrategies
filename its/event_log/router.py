from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from its.authz.context import AuthContext
from its.event_log.repository import (
    EventLogFilters,
    list_event_log_filter_options,
    list_event_logs,
)
from its.event_log.schemas import (
    EVENT_LOG_COLUMNS,
    EventLogFilterOptionsResponse,
    EventLogListResponse,
)
from its.event_log.security import require_event_log_access_token
from its.event_log.storage import get_event_log_session

router = APIRouter(tags=["Event Logs"])


@router.get("/events", response_model=EventLogListResponse)
def events(
    _: Annotated[AuthContext, Depends(require_event_log_access_token)],
    session: Annotated[Session, Depends(get_event_log_session)],
    id: Annotated[int | None, Query(ge=1)] = None,
    date_time_from: datetime | None = None,
    date_time_to: datetime | None = None,
    service: str | None = None,
    user: str | None = None,
    http_action: str | None = None,
    ip_address: str | None = None,
    path: str | None = None,
    header: str | None = None,
    body: str | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EventLogListResponse:
    items, total = list_event_logs(
        session,
        EventLogFilters(
            id=id,
            date_time_from=date_time_from,
            date_time_to=date_time_to,
            service=service,
            user=user,
            http_action=http_action,
            ip_address=ip_address,
            path=path,
            header=header,
            body=body,
        ),
        limit=limit,
        offset=offset,
    )
    return EventLogListResponse(
        columns=EVENT_LOG_COLUMNS,
        items=items,
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/events/filter-options", response_model=EventLogFilterOptionsResponse)
def event_filter_options(
    _: Annotated[AuthContext, Depends(require_event_log_access_token)],
    session: Annotated[Session, Depends(get_event_log_session)],
) -> EventLogFilterOptionsResponse:
    services, users = list_event_log_filter_options(session)
    return EventLogFilterOptionsResponse(services=services, users=users)
