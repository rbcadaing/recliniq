"""Import every ORM model module here so ``Base.metadata`` is complete for Alembic."""

from app.infrastructure.accounts import models as accounts_models  # noqa: F401
from app.infrastructure.db import soft_delete  # noqa: F401  (registers session-wide listeners)
from app.infrastructure.db.base import Base

__all__ = ["Base"]
