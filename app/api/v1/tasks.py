"""Task definitions describe metadata; no task is executed by this API."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.api.dependencies import DatabaseSession
from app.db.models import TaskDefinition
from app.schemas import Page, TaskCreate, TaskRead, TaskUpdate
from app.services.inventory import InventoryService

router = APIRouter(prefix="/tasks", tags=["Task definitions"])


@router.post("", response_model=TaskRead, status_code=201)
def create_task(payload: TaskCreate, session: DatabaseSession, response: Response):
    resource = InventoryService(session, TaskDefinition).create(payload)
    response.headers["Location"] = f"/api/v1/tasks/{resource.id}"
    return resource


@router.get("", response_model=Page[TaskRead])
def list_tasks(
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    enabled: bool | None = None,
    agent_id: UUID | None = None,
):
    filters = {
        key: value
        for key, value in {"enabled": enabled, "agent_id": agent_id}.items()
        if value is not None
    }
    return InventoryService(session, TaskDefinition).list(filters, limit, offset)


@router.get("/{resource_id}", response_model=TaskRead)
def get_task(resource_id: UUID, session: DatabaseSession):
    return InventoryService(session, TaskDefinition).get(resource_id)


@router.patch("/{resource_id}", response_model=TaskRead)
def update_task(resource_id: UUID, payload: TaskUpdate, session: DatabaseSession):
    return InventoryService(session, TaskDefinition).update(resource_id, payload)


@router.delete("/{resource_id}", status_code=204)
def delete_task(resource_id: UUID, session: DatabaseSession, version: Annotated[int, Query(ge=1)]):
    InventoryService(session, TaskDefinition).delete(resource_id, version)
    return Response(status_code=204)
