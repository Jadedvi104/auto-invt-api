"""Agent API contracts."""

from typing import Literal
from uuid import UUID

from pydantic import ConfigDict

from app.schemas.common import (
    AwareTimestamp,
    ReadModel,
    RequestModel,
    ResourceName,
    UpdateModel,
)

AgentState = Literal["online", "offline", "disabled"]


class AgentCreate(RequestModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "host_id": "a2dfa3a0-0fcb-4ade-b78b-90103c43cc19",
                    "name": "inventory-runner",
                    "state": "online",
                    "last_seen_at": "2026-10-16T08:30:00Z",
                }
            ]
        }
    )

    host_id: UUID
    name: ResourceName
    state: AgentState = "offline"
    last_seen_at: AwareTimestamp | None = None


class AgentUpdate(UpdateModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"version": 1, "state": "offline", "last_seen_at": None}]}
    )

    host_id: UUID | None = None
    name: ResourceName | None = None
    state: AgentState | None = None
    last_seen_at: AwareTimestamp | None = None


class AgentRead(ReadModel):
    host_id: UUID
    name: str
    state: AgentState
    last_seen_at: AwareTimestamp | None
