from datetime import UTC, datetime

from sqlalchemy import BigInteger, DateTime, Identity, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class EventLogBase(DeclarativeBase):
    pass


def utc_now() -> datetime:
    return datetime.now(UTC)


class EventLogEntry(EventLogBase):
    __tablename__ = "event_logs"

    id: Mapped[int] = mapped_column(
        BigInteger,
        Identity(always=False),
        primary_key=True,
    )
    date_time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        index=True,
    )
    service: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    user: Mapped[str] = mapped_column("user", Text, nullable=False, index=True)
    http_action: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    ip_address: Mapped[str] = mapped_column(
        String(128), nullable=False, default="unknown", index=True
    )
    path: Mapped[str] = mapped_column(Text, nullable=False)
    header: Mapped[dict[str, str]] = mapped_column(JSONB, nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
