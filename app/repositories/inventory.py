"""Bound ORM operations; transaction ownership belongs to the service layer."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session


class InventoryRepository:
    def __init__(self, session: Session, model: type):
        self.session = session
        self.model = model

    def get(self, resource_id: UUID):
        return self.session.get(self.model, resource_id)

    def create(self, values: dict[str, Any]):
        resource = self.model(**values)
        self.session.add(resource)
        self.session.flush()
        return resource

    def list(self, filters: dict, limit: int, offset: int):
        predicates = [getattr(self.model, key) == value for key, value in filters.items()]
        total = self.session.scalar(select(func.count()).select_from(self.model).where(*predicates))
        query = (
            select(self.model)
            .where(*predicates)
            .order_by(self.model.created_at, self.model.id)
            .limit(limit)
            .offset(offset)
        )
        return self.session.scalars(query).all(), total

    def update(self, resource_id: UUID, version: int, values: dict[str, Any]):
        statement = (
            update(self.model)
            .where(self.model.id == resource_id, self.model.version == version)
            .values(**values, version=self.model.version + 1, updated_at=datetime.now(UTC))
            .returning(self.model)
            .execution_options(synchronize_session=False, populate_existing=True)
        )
        return self.session.scalars(statement).one_or_none()

    def delete(self, resource_id: UUID, version: int) -> bool:
        statement = delete(self.model).where(
            self.model.id == resource_id, self.model.version == version
        )
        return self.session.execute(statement).rowcount == 1
