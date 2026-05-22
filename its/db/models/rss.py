from datetime import datetime

from sqlalchemy import DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from its.db.base import Base


class RSSItem(Base):
    __tablename__ = "rss_items"

    pub_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        primary_key=True,
    )
    title: Mapped[str] = mapped_column(Text, primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(Text, primary_key=True)
