"""Utilidades compartidas por los modelos ORM."""

import uuid
from datetime import datetime, timezone


def nuevo_id() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc)
