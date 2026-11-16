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


def upgrade() -> None:
    op.add_column("solicitudes", sa.Column("autor_nombre", sa.String(length=160), nullable=True))
    # Las solicitudes que ya existen conservan el nombre de su autor actual.
    op.execute(
        "UPDATE solicitudes SET autor_nombre = "
        "(SELECT nombre FROM usuarios WHERE usuarios.id = solicitudes.usuario_id)"
    )
    op.alter_column("solicitudes", "usuario_id", existing_type=sa.String(length=36), nullable=True)
    op.alter_column("preselecciones", "usuario_id", existing_type=sa.String(length=36), nullable=True)


def downgrade() -> None:
    # Falla si ya hay solicitudes de cuentas borradas: hay que atribuirlas antes.
    op.alter_column("preselecciones", "usuario_id", existing_type=sa.String(length=36), nullable=False)
    op.alter_column("solicitudes", "usuario_id", existing_type=sa.String(length=36), nullable=False)
    op.drop_column("solicitudes", "autor_nombre")
