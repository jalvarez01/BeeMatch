"""indices de busqueda (HNSW y GIN)

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-11
"""
from typing import Sequence, Union

from alembic import op

from backend.infrastructure.persistence.database import INDICES_DE_BUSQUEDA

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # IF NOT EXISTS: una base que ya los tenía (creada antes por init_db) no falla.
    for sentencia in INDICES_DE_BUSQUEDA.values():
        op.execute(sentencia)


def downgrade() -> None:
    for nombre in INDICES_DE_BUSQUEDA:
        op.execute(f"DROP INDEX IF EXISTS {nombre}")
