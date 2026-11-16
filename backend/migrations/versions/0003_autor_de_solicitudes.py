"""autor de las solicitudes sin depender de la cuenta

Borrar el perfil de una persona no debe borrar su historial: la solicitud guarda
el nombre de su autor y deja de exigir que la cuenta exista.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-16
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columnas(tabla: str) -> dict:
    return {c["name"]: c for c in sa.inspect(op.get_bind()).get_columns(tabla)}


def _hacer_opcional(tabla: str, columna: str) -> None:
    """Solo si hoy es obligatoria: así una base ya al día no pide un bloqueo de tabla."""
    if not _columnas(tabla)[columna]["nullable"]:
        op.alter_column(tabla, columna, existing_type=sa.String(length=36), nullable=True)


def upgrade() -> None:
    # Una base creada antes de Alembic (con create_all) ya trae lo nuevo: no se repite.
    if "autor_nombre" not in _columnas("solicitudes"):
        op.add_column("solicitudes", sa.Column("autor_nombre", sa.String(length=160), nullable=True))
        # Las solicitudes que ya existen conservan el nombre de su autor actual.
        op.execute(
            "UPDATE solicitudes SET autor_nombre = "
            "(SELECT nombre FROM usuarios WHERE usuarios.id = solicitudes.usuario_id)"
        )
    _hacer_opcional("solicitudes", "usuario_id")
    _hacer_opcional("preselecciones", "usuario_id")


def downgrade() -> None:
    # Falla si ya hay solicitudes de cuentas borradas: hay que atribuirlas antes.
    op.alter_column("preselecciones", "usuario_id", existing_type=sa.String(length=36), nullable=False)
    op.alter_column("solicitudes", "usuario_id", existing_type=sa.String(length=36), nullable=False)
    op.drop_column("solicitudes", "autor_nombre")
