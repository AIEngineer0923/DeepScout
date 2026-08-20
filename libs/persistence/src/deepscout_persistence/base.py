from sqlalchemy import Enum
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def pg_enum(enum_cls: type, name: str) -> Enum:
    """Map StrEnum values to PostgreSQL native enum labels."""

    return Enum(
        enum_cls,
        name=name,
        values_callable=lambda members: [member.value for member in members],
    )
