"""Test-only models for exercising soft delete before any real application table exists.

They live on their own declarative base, so they never enter ``Base.metadata``, migrations, or
the schema drift check. Integration tests create their tables inside a rolled-back transaction.
"""

import uuid

from sqlalchemy import ForeignKey, MetaData, String, Uuid
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.infrastructure.db.base import NAMING_CONVENTION, SoftDeleteMixin, soft_unique_index


class WidgetBase(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Widget(SoftDeleteMixin, WidgetBase):
    __tablename__ = "test_widgets"
    __table_args__ = (soft_unique_index("uq_test_widgets_code_active", "code"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(50))
    parts: Mapped[list["WidgetPart"]] = relationship(back_populates="widget", lazy="raise")


class WidgetPart(SoftDeleteMixin, WidgetBase):
    __tablename__ = "test_widget_parts"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    widget_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("test_widgets.id"))
    name: Mapped[str] = mapped_column(String(50))
    widget: Mapped[Widget] = relationship(back_populates="parts", lazy="raise")
