from app.core.db import Base
from sqlalchemy import Column, Integer, String


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    msg_id = Column(String, nullable=False, default=False)
    from_user = Column(String, nullable=False, default="False")
    to_user = Column(String, nullable=False, default="False")
    content = Column(String, nullable=False, default="False")
    type = Column(String, nullable=False, default="False")
