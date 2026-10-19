"""Utilidades compartidas por los modelos ORM."""

import uuid
from datetime import UTC, datetime


def nuevo_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(UTC)
