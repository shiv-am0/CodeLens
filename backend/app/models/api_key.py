import uuid
from datetime import datetime
from sqlalchemy import Column, String, Boolean, DateTime, Integer, Text
from app.core.database import Base


class ApiKey(Base):
    __tablename__ = "api_keys"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    key_encrypted = Column(Text, nullable=False)
    key_prefix = Column(String(8), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_used = Column(DateTime, nullable=True)
    usage_count = Column(Integer, default=0)
