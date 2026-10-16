"""Host API contracts."""

from typing import Literal

from pydantic import ConfigDict

from app.schemas.common import Environment, Hostname, ReadModel, RequestModel, UpdateModel

HostStatus = Literal["active", "inactive", "maintenance"]


class HostCreate(RequestModel):
    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"hostname": "worker-01.example.net", "environment": "dev", "status": "active"}
            ]
        }
    )

    hostname: Hostname
    environment: Environment = "dev"
    status: HostStatus = "active"


class HostUpdate(UpdateModel):
    model_config = ConfigDict(
        json_schema_extra={"examples": [{"version": 1, "status": "maintenance"}]}
    )

    hostname: Hostname | None = None
    environment: Environment | None = None
    status: HostStatus | None = None


class HostRead(ReadModel):
    hostname: str
    environment: str
    status: HostStatus
