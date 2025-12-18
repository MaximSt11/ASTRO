from sqlalchemy import BigInteger, String, ForeignKey, func, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from datetime import datetime


class AnalyticsEvent(Base):
    __tablename__ = "analytics_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))

    # Тип события: "command_start", "generate_image", "buy_subscription"
    event_type: Mapped[str] = mapped_column(String, index=True)

    # Дополнительные данные (например, какой тариф выбрали)
    details: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())