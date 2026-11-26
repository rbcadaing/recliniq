"""Import every ORM model module here so ``Base.metadata`` is complete for Alembic.

No models exist yet; feature stories add imports below.
"""

from app.infrastructure.db.base import Base

__all__ = ["Base"]
