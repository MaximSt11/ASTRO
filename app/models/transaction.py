from sqlalchemy import BigInteger, String, Integer, ForeignKey, func, DateTime
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base
from datetime import datetime


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"))

    amount: Mapped[int] = mapped_column(Integer)  # Сумма в копейках/центах
    currency: Mapped[str] = mapped_column(String, default="RUB")
    status: Mapped[str] = mapped_column(String, default="pending")  # pending, success, failed

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())