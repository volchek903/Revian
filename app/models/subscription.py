from app.core.db import Base
from sqlalchemy import Column, Integer, String, DateTime, Boolean


class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String, nullable=False)
    type = Column(String, default="User", nullable=False)
    status = Column(Boolean, default=0)
    create_at = Column(DateTime, nullable=False)
