"""Shared SQLAlchemy metadata.

Alembic is the only component allowed to turn this metadata into database DDL.
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase


CONSTRAINT_NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Declarative base used by repositories and Alembic."""

    metadata = MetaData(naming_convention=CONSTRAINT_NAMING_CONVENTION)


# Importing the models registers every canonical table on the shared metadata.
# Applications still must run Alembic explicitly; no runtime create_all is allowed.
from . import models as _models  # noqa: E402,F401
