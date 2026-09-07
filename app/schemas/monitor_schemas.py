from pydantic import BaseModel

from datetime import datetime

from app.db.models.monitor import MonitorStatus


class MonitorSchema(BaseModel):
    id: int
    name: str

    url: str
    method: str

    interval_seconds: int
    timeout_seconds: int
    expected_status: int
    current_status: MonitorStatus | None

    last_checked_at: datetime | None
    last_response_ms: int | None

    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }

class MonitorCreateSchema(BaseModel):
    name: str
    url: str
    method: str

    interval_seconds: int
    timeout_seconds: int
    expected_status: int
  
    model_config = {
        "from_attributes": True
    }


class MonitorUpdateSchema(BaseModel):
    name: str | None = None
    url: str | None = None
    method: str | None = None

    interval_seconds: int | None = None
    timeout_seconds: int | None = None
    expected_status: int | None = None
  
    model_config = {
        "from_attributes": True
    }
    