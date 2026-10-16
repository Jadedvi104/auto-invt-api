"""Domain rules, optimistic concurrency, and explicit transaction boundaries."""

from uuid import UUID

from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Agent, Host
from app.repositories.inventory import InventoryRepository


class DomainError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


class InventoryService:
    def __init__(self, session: Session, model: type):
        self.session = session
        self.repository = InventoryRepository(session, model)

    def get(self, resource_id: UUID):
        resource = self.repository.get(resource_id)
        if resource is None:
            raise DomainError(404, "not_found", "The requested resource does not exist.")
        return resource

    def list(self, filters: dict, limit: int, offset: int):
        items, total = self.repository.list(filters, limit, offset)
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    def _validate_references(self, values: dict):
        for field, model in (("host_id", Host), ("agent_id", Agent)):
            value = values.get(field)
            if value is not None and self.session.get(model, value) is None:
                raise DomainError(
                    422, "invalid_reference", f"{field} refers to an unknown resource."
                )

    def _conflict_or_missing(self, resource_id: UUID):
        self.get(resource_id)
        raise DomainError(
            409, "version_conflict", "The resource changed; reload its current version."
        )

    def create(self, payload: BaseModel):
        try:
            values = payload.model_dump()
            self._validate_references(values)
            resource = self.repository.create(values)
            self.session.commit()
            return resource
        except IntegrityError as exc:
            self.session.rollback()
            raise DomainError(
                409,
                "constraint_conflict",
                "A uniqueness or reference constraint prevents this change.",
            ) from exc

    def update(self, resource_id: UUID, payload: BaseModel):
        try:
            values = payload.model_dump(exclude_unset=True)
            version = values.pop("version")
            self._validate_references(values)
            resource = self.repository.update(resource_id, version, values)
            if resource is None:
                self._conflict_or_missing(resource_id)
            self.session.commit()
            return resource
        except IntegrityError as exc:
            self.session.rollback()
            raise DomainError(
                409,
                "constraint_conflict",
                "A uniqueness or reference constraint prevents this change.",
            ) from exc

    def delete(self, resource_id: UUID, version: int):
        try:
            if not self.repository.delete(resource_id, version):
                self._conflict_or_missing(resource_id)
            self.session.commit()
        except IntegrityError as exc:
            self.session.rollback()
            raise DomainError(
                409, "resource_in_use", "Delete dependent resources before deleting this resource."
            ) from exc
