"""
Copia de lo que se analizó en cada ejecución (HU-12, HU-15).

La solicitud se puede editar y volver a ejecutar. Para que cada ejecución
conserve los criterios, el cliente y el proyecto con los que corrió, se guarda
una copia junto a la búsqueda en el momento de encolarla.
"""

from typing import Optional

from pydantic import ValidationError

from backend.infrastructure.persistence.models.busqueda import BusquedaModel
from backend.infrastructure.persistence.models.solicitud import CriterioModel, SolicitudModel
from backend.infrastructure.persistence.repositories.cliente_repo import (
    ClienteRepository,
    ProyectoRepository,
)
from backend.schemas.busqueda import ParametrosBusqueda
from backend.schemas.solicitud import CriterioBase


def parametros_de_solicitud(
    solicitud: SolicitudModel,
    criterios: list[CriterioModel],
    clientes: ClienteRepository,
    proyectos: ProyectoRepository,
) -> ParametrosBusqueda:
    cliente = clientes.get_by_id(solicitud.cliente_id) if solicitud.cliente_id else None
    proyecto = proyectos.get_by_id(solicitud.proyecto_id) if solicitud.proyecto_id else None
    return ParametrosBusqueda(
        descripcion_libre=solicitud.descripcion_libre or "",
        rol_buscado=solicitud.rol_buscado,
        experiencia_min=solicitud.experiencia_min,
        cliente_id=solicitud.cliente_id,
        cliente=cliente.nombre if cliente else None,
        proyecto_id=solicitud.proyecto_id,
        proyecto=proyecto.nombre if proyecto else None,
        criterios=[
            CriterioBase.model_validate(
                {"tipo": c.tipo, "valor": c.valor, "obligatorio": c.obligatorio, "peso": c.peso}
            )
            for c in criterios
        ],
    )


def leer_parametros(busqueda: BusquedaModel) -> Optional[ParametrosBusqueda]:
    """None en las ejecuciones anteriores a HU-15, o si la copia guardada no se puede leer."""
    if not busqueda.parametros_json:
        return None
    try:
        return ParametrosBusqueda.model_validate_json(busqueda.parametros_json)
    except ValidationError:
        return None
