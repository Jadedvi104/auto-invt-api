"""Versioned automation agent endpoints."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.api.dependencies import DatabaseSession
from app.db.models import Agent
from app.schemas import AgentCreate, AgentRead, AgentUpdate, Page
from app.services.inventory import InventoryService

router = APIRouter(prefix="/agents", tags=["Agents"])


@router.post("", response_model=AgentRead, status_code=201)
def create_agent(payload: AgentCreate, session: DatabaseSession, response: Response):
    resource = InventoryService(session, Agent).create(payload)
    response.headers["Location"] = f"/api/v1/agents/{resource.id}"
    return resource


@router.get("", response_model=Page[AgentRead])
def list_agents(
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    state: Literal["online", "offline", "disabled"] | None = None,
    host_id: UUID | None = None,
):
    filters = {
        key: value
        for key, value in {"state": state, "host_id": host_id}.items()
        if value is not None
    }
    return InventoryService(session, Agent).list(filters, limit, offset)


@router.get("/{resource_id}", response_model=AgentRead)
def get_agent(resource_id: UUID, session: DatabaseSession):
    return InventoryService(session, Agent).get(resource_id)


@router.patch("/{resource_id}", response_model=AgentRead)
def update_agent(resource_id: UUID, payload: AgentUpdate, session: DatabaseSession):
    return InventoryService(session, Agent).update(resource_id, payload)


@router.delete("/{resource_id}", status_code=204)
def delete_agent(resource_id: UUID, session: DatabaseSession, version: Annotated[int, Query(ge=1)]):
    InventoryService(session, Agent).delete(resource_id, version)
    return Response(status_code=204)
