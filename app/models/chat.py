from app.core.db import Base
from sqlalchemy import Boolean, Column, Integer, String, DateTime
from sqlalchemy.sql import func


class Chat(Base):
    __tablename__ = "chats"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String, nullable=False)
    user_id = Column(String, nullable=False)
    status = Column(Boolean, default=True)
    create_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),  # ✅ БД сама проставит текущий timestamp
        nullable=False,
    )
