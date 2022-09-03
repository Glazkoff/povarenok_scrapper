from datetime import datetime
from sqlalchemy import (
    String,
    Integer,
    Column,
    DateTime,
)

from .base import Base


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    tg_chat_id = Column(String(255), nullable=False, unique=True)
    created_on = Column(DateTime(), default=datetime.now)
    updated_on = Column(DateTime(), default=datetime.now)
