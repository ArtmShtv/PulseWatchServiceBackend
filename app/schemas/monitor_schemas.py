from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from app.core.url_safety import check_url_host
from app.db.models.monitor import MonitorStatus

HttpMethod = Literal["GET", "HEAD"]


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
    name: Annotated[
        str,
        Field(min_length=1, max_length=100)
    ]
    url: Annotated[
        HttpUrl,
        Field()
    ]
    method: HttpMethod = "GET"

    interval_seconds: Annotated[
        int,
        Field(ge=60, le=86400)
    ]
    timeout_seconds: Annotated[
        int,
        Field(ge=1, le=60)
    ]
    expected_status: Annotated[
        int,
        Field(ge=100, le=599)
    ] = 200

    model_config = {
        "from_attributes": True
    }

    @field_validator("url")
    @classmethod
    def url_must_be_public(cls, v: HttpUrl) -> HttpUrl:
        check_url_host(str(v))  # UnsafeTargetError is a ValueError -> 422
        return v

    @field_validator("timeout_seconds")
    @classmethod
    def timeout_lt_interval(cls, v, info):
        interval = info.data.get("interval_seconds")
        if interval is not None and v >= interval:
            raise ValueError("timeout_seconds must be less than interval_seconds")
        return v


class MonitorUpdateSchema(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=100)] | None = None
    url: HttpUrl | None = None
    method: HttpMethod | None = None

    interval_seconds: Annotated[int, Field(ge=60, le=86400)] | None = None
    timeout_seconds: Annotated[int, Field(ge=1, le=60)] | None = None
    expected_status: Annotated[int, Field(ge=100, le=599)] | None = None

    model_config = {
        "from_attributes": True
    }

    @field_validator("url")
    @classmethod
    def url_must_be_public(cls, v: HttpUrl | None) -> HttpUrl | None:
        if v is not None:
            check_url_host(str(v))
        return v

    @model_validator(mode="after")
    def timeout_lt_interval(self):
        if (
            self.timeout_seconds is not None
            and self.interval_seconds is not None
            and self.timeout_seconds >= self.interval_seconds
        ):
            raise ValueError("timeout_seconds must be less than interval_seconds")
        return self
    