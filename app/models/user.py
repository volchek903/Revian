from app.core.db import Base
from sqlalchemy import Column, String, DateTime
from sqlalchemy import func


class User(Base):
    __tablename__ = "users"
    tgLog = Column(String, default="None")
    ref_code = Column(String, nullable=False)
    referral_id = Column(String)
    create_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    tgID = Column(String, primary_key=True)
    connection_id = Column(String)
