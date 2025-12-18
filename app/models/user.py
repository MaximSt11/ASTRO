from sqlalchemy import BigInteger, String, Boolean, DateTime, Date, Time, func, ForeignKey, Text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from datetime import datetime, date, time


class User(Base):
    __tablename__ = "users"

    # Основные данные
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    username: Mapped[str | None] = mapped_column(String, nullable=True)
    full_name: Mapped[str | None] = mapped_column(String, nullable=True)
    referrer_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=True)

    # Астро-профиль
    birth_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    birth_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    birth_place: Mapped[str | None] = mapped_column(String, nullable=True)
    theme: Mapped[str] = mapped_column(String, default="default")

    # --- КЭШ ПРОГНОЗОВ ---
    natal_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)
    numerology_analysis: Mapped[str | None] = mapped_column(Text, nullable=True)

    daily_advice: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_advice_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # НОВОЕ: Аффирмация
    daily_affirmation: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_affirmation_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())