"""Shared request validation and response contracts."""

import re
from datetime import datetime
from typing import Annotated, Generic, TypeVar
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    model_validator,
)


def valid_hostname(value: str) -> str:
    value = value.lower()
    labels = value.split(".")
    if any(not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", label) for label in labels):
        raise ValueError(
            "hostname must contain valid DNS labels with no leading or trailing hyphens"
        )
    return value


def aware_timestamp(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must include a timezone offset")
    return value


Hostname = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=253),
    AfterValidator(valid_hostname),
]
Environment = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=64)]
ResourceName = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
]
AwareTimestamp = Annotated[datetime, AfterValidator(aware_timestamp)]
Version = Annotated[int, Field(strict=True, ge=1)]


class RequestModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class UpdateModel(RequestModel):
    version: Version

    @model_validator(mode="after")
    def require_changes(self):
        editable_fields = self.model_fields_set - {"version"}
        if not editable_fields:
            raise ValueError("provide at least one editable field along with version")
        nullable_fields = {"agent_id", "last_seen_at"}
        for field in editable_fields - nullable_fields:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")
        return self


class ReadModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    version: int
    created_at: datetime
    updated_at: datetime


T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int
