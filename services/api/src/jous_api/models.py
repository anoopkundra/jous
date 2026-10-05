"""Foundational identity and ownership records only; no workflows or vendor coupling."""

from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .persistence import Base, Record


class User(Record, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("auth_issuer", "auth_subject", name="uq_users_auth_identity"),
        CheckConstraint("(auth_issuer IS NULL AND auth_subject IS NULL) OR "
                        "(auth_issuer IS NOT NULL AND auth_subject IS NOT NULL AND "
                        "length(btrim(auth_issuer)) > 0 AND length(btrim(auth_subject)) > 0)",
                        name="auth_identity_pair"),
        CheckConstraint("length(btrim(status)) > 0", name="status_nonblank"),
    )
    auth_issuer: Mapped[str | None] = mapped_column(String(255))
    auth_subject: Mapped[str | None] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), server_default="active")


class Organization(Record, Base):
    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint("length(btrim(name)) > 0", name="name_nonblank"),
        CheckConstraint("length(btrim(status)) > 0", name="status_nonblank"),
    )
    name: Mapped[str] = mapped_column(String(255))
    status: Mapped[str] = mapped_column(String(32), server_default="active")


class OrganizationMembership(Record, Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_organization_memberships_organization_user"),
        Index("ix_organization_memberships_user_id", "user_id"),
        CheckConstraint("length(btrim(role)) > 0", name="role_nonblank"),
        CheckConstraint("length(btrim(status)) > 0", name="status_nonblank"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"))
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    role: Mapped[str] = mapped_column(String(32), server_default="member")
    status: Mapped[str] = mapped_column(String(32), server_default="active")


class Project(Record, Base):
    __tablename__ = "projects"
    __table_args__ = (
        Index("ix_projects_organization_id", "organization_id"),
        CheckConstraint("length(btrim(name)) > 0", name="name_nonblank"),
        CheckConstraint("length(btrim(status)) > 0", name="status_nonblank"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT"))
    name: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(32), server_default="active")
