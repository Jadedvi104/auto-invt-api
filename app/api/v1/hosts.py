"""Versioned host endpoints."""

from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.api.dependencies import DatabaseSession
from app.db.models import Host
from app.schemas import HostCreate, HostRead, HostUpdate, Page
from app.services.inventory import InventoryService

router = APIRouter(prefix="/hosts", tags=["Hosts"])


@router.post("", response_model=HostRead, status_code=201)
def create_host(payload: HostCreate, session: DatabaseSession, response: Response):
    resource = InventoryService(session, Host).create(payload)
    response.headers["Location"] = f"/api/v1/hosts/{resource.id}"
    return resource


@router.get("", response_model=Page[HostRead])
def list_hosts(
    session: DatabaseSession,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    status: Literal["active", "inactive", "maintenance"] | None = None,
    environment: Annotated[str | None, Query(min_length=1, max_length=64)] = None,
):
    filters = {
        key: value
        for key, value in {"status": status, "environment": environment}.items()
        if value is not None
    }
    return InventoryService(session, Host).list(filters, limit, offset)


@router.get("/{resource_id}", response_model=HostRead)
def get_host(resource_id: UUID, session: DatabaseSession):
    return InventoryService(session, Host).get(resource_id)


@router.patch("/{resource_id}", response_model=HostRead)
def update_host(resource_id: UUID, payload: HostUpdate, session: DatabaseSession):
    return InventoryService(session, Host).update(resource_id, payload)


@router.delete("/{resource_id}", status_code=204)
def delete_host(resource_id: UUID, session: DatabaseSession, version: Annotated[int, Query(ge=1)]):
    InventoryService(session, Host).delete(resource_id, version)
    return Response(status_code=204)
