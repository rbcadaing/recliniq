"""Repository base for soft-deletable models. Feature repositories subclass it."""

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, ClassVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.base import SoftDeleteMixin
from app.infrastructure.db.soft_delete import INCLUDE_DELETED


class SoftDeleteRepository[T: SoftDeleteMixin]:
    model: ClassVar[type[Any]]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, entity_id: Any, *, include_deleted: bool = False) -> T | None:
        # A SELECT (not ``session.get``) so an entity soft-deleted earlier in this session,
        # and still in the identity map, is not returned.
        statement = (
            select(self.model)
            .where(self.model.id == entity_id)
            .execution_options(**{INCLUDE_DELETED: include_deleted})
        )
        result: T | None = await self.session.scalar(statement)
        return result

    async def list_deleted(self) -> Sequence[T]:
        statement = (
            select(self.model)
            .where(self.model.deleted_at.is_not(None))
            .order_by(self.model.deleted_at.desc())
            .execution_options(**{INCLUDE_DELETED: True})
        )
        return list(await self.session.scalars(statement))

    async def soft_delete(self, entity: T, actor_id: uuid.UUID | None) -> None:
        """Mark ``entity`` deleted. ``actor_id`` is ``None`` for system actions. Idempotent."""
        if entity.is_deleted:
            return
        entity.deleted_at = datetime.now(UTC)
        entity.deleted_by = actor_id
        await self.session.flush()

    async def restore(self, entity: T) -> None:
        """Make ``entity`` visible again. Restoring an active entity changes nothing."""
        if not entity.is_deleted:
            return
        entity.deleted_at = None
        entity.deleted_by = None
        await self.session.flush()
