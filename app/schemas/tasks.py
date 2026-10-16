"""Task definitions store metadata only; the API never executes commands."""

from typing import Any
from uuid import UUID

from pydantic import ConfigDict, Field, StrictBool

from app.schemas.common import ReadModel, RequestModel, ResourceName, UpdateModel


class TaskCreate(RequestModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "agent_id": "7aa5f4ef-b458-4705-adb6-697af85eceb4",
                    "name": "nightly-inventory-audit",
                    "command_template_metadata": {
                        "template": "inventory-audit-v1",
                        "parameters": {"scope": "packages"},
                    },
                    "enabled": True,
                }
            ]
        }
    )

    agent_id: UUID | None = None
    name: ResourceName
    command_template_metadata: dict[str, Any] = Field(default_factory=dict)
    enabled: StrictBool = True


class TaskUpdate(UpdateModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"version": 1, "agent_id": None, "enabled": False}]}
    )

    agent_id: UUID | None = None
    name: ResourceName | None = None
    command_template_metadata: dict[str, Any] | None = None
    enabled: StrictBool | None = None


class TaskRead(ReadModel):
    agent_id: UUID | None
    name: str
    command_template_metadata: dict[str, Any]
    enabled: bool
