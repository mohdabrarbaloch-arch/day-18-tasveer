"""ORM models: users, generations, and the images they produce."""

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    credits: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )

    generations: Mapped[list["Generation"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Generation(Base):
    """One prompt submission. Produces `grid_size` images."""

    __tablename__ = "generations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )

    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    negative_prompt: Mapped[str] = mapped_column(Text, default="", nullable=False)
    style: Mapped[str] = mapped_column(String(40), default="cinematic", nullable=False)
    aspect_ratio: Mapped[str] = mapped_column(String(10), default="1:1", nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    credits_spent: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    provider: Mapped[str] = mapped_column(String(20), default="local", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), index=True
    )

    user: Mapped["User"] = relationship(back_populates="generations")
    images: Mapped[list["Image"]] = relationship(
        back_populates="generation", cascade="all, delete-orphan"
    )


class Image(Base):
    """A single rendered image belonging to a generation."""

    __tablename__ = "images"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    generation_id: Mapped[int] = mapped_column(
        ForeignKey("generations.id", ondelete="CASCADE"), index=True, nullable=False
    )

    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    seed: Mapped[int] = mapped_column(Integer, nullable=False)
    index: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    upscaled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )

    generation: Mapped["Generation"] = relationship(back_populates="images")
