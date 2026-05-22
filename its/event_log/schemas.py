from datetime import datetime

from pydantic import BaseModel, ConfigDict

EVENT_LOG_COLUMNS = [
    "id",
    "date_time",
    "service",
    "user",
    "http_action",
    "ip_address",
    "path",
    "header",
    "body",
]


class EventLogEntryRead(BaseModel):
    id: int
    date_time: datetime
    service: str
    user: str
    http_action: str
    ip_address: str
    path: str
    header: dict[str, str]
    body: str | None

    model_config = ConfigDict(from_attributes=True)


class EventLogListResponse(BaseModel):
    columns: list[str]
    items: list[EventLogEntryRead]
    total: int
    limit: int
    offset: int


class EventLogFilterOptionsResponse(BaseModel):
    services: list[str]
    users: list[str]
