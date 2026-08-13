"""Gestión de solicitudes de staffing (HU-08 a HU-15)."""

from typing import Optional

from sqlalchemy.orm import Session

from backend.infrastructure.persistence.models.solicitud import (
    ESTADO_BORRADOR,
    ESTADO_PROCESADA,
)
from backend.infrastructure.persistence.repositories.busqueda_repo import BusquedaRepository
from backend.infrastructure.persistence.repositories.cliente_repo import (
    ClienteRepository,
    ProyectoRepository,
)
from backend.infrastructure.persistence.repositories.solicitud_repo import SolicitudRepository
from backend.infrastructure.persistence.repositories.usuario_repo import UsuarioRepository
from backend.schemas.solicitud import (
    CriterioResponse,
    SolicitudCreate,
    SolicitudResponse,
    SolicitudUpdate,
)


class SolicitudService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = SolicitudRepository(db)
        self.clientes = ClienteRepository(db)
        self.proyectos = ProyectoRepository(db)
        self.usuarios = UsuarioRepository(db)
        self.busquedas = BusquedaRepository(db)

    def crear(self, datos: SolicitudCreate, usuario_id: str) -> SolicitudResponse:
        cliente_id, proyecto_id = self._resolver_cliente(datos.cliente, datos.proyecto)

        solicitud = self.repo.crear(
            descripcion_libre=datos.descripcion_libre,
            rol_buscado=datos.rol_buscado,
            experiencia_min=datos.experiencia_min,
            estado=ESTADO_BORRADOR,
            cliente_id=cliente_id,
            proyecto_id=proyecto_id,
            usuario_id=usuario_id,
        )
        self.repo.reemplazar_criterios(solicitud.id, [c.model_dump() for c in datos.criterios])
        return self._enriquecer(solicitud)

    def actualizar(self, solicitud_id: str, datos: SolicitudUpdate) -> Optional[SolicitudResponse]:
        """
        HU-15: editar una solicitud procesada no borra su historial; la nueva
        ejecución genera otra Busqueda (RD1).
        """
        solicitud = self.repo.get_by_id(solicitud_id)
        if not solicitud:
            return None

        cliente_id, proyecto_id = self._resolver_cliente(datos.cliente, datos.proyecto)
        self.repo.actualizar(
            solicitud,
            descripcion_libre=datos.descripcion_libre,
            rol_buscado=datos.rol_buscado,
            experiencia_min=datos.experiencia_min,
            cliente_id=cliente_id,
            proyecto_id=proyecto_id,
        )
        if datos.criterios is not None:
            self.repo.reemplazar_criterios(solicitud.id, [c.model_dump() for c in datos.criterios])
        return self._enriquecer(solicitud)

    def duplicar(self, solicitud_id: str, usuario_id: str) -> Optional[SolicitudResponse]:
        """HU-14: crea una solicitud nueva con los criterios precargados."""
        original = self.repo.get_by_id(solicitud_id)
        if not original:
            return None

        copia = self.repo.crear(
            descripcion_libre=original.descripcion_libre,
            rol_buscado=original.rol_buscado,
            experiencia_min=original.experiencia_min,
            estado=ESTADO_BORRADOR,
            cliente_id=original.cliente_id,
            proyecto_id=original.proyecto_id,
            usuario_id=usuario_id,
        )
        criterios = [
            {"tipo": c.tipo, "valor": c.valor, "obligatorio": c.obligatorio, "peso": c.peso}
            for c in self.repo.listar_criterios(solicitud_id)
        ]
        self.repo.reemplazar_criterios(copia.id, criterios)
        return self._enriquecer(copia)

    def obtener(self, solicitud_id: str) -> Optional[SolicitudResponse]:
        solicitud = self.repo.get_by_id(solicitud_id)
        return self._enriquecer(solicitud) if solicitud else None

    def historial(
        self,
        estado: Optional[str] = None,
        texto: Optional[str] = None,
        pagina: int = 1,
        por_pagina: int = 10,
    ) -> tuple[list[SolicitudResponse], int]:
        """HU-13: historial filtrable y paginado."""
        solicitudes = self.repo.listar(
            estado=estado, texto=texto, limite=por_pagina, desplazamiento=(pagina - 1) * por_pagina
        )
        return [self._enriquecer(s) for s in solicitudes], self.repo.contar(estado)

    # --- Internos ------------------------------------------------------------

    def _resolver_cliente(
        self, cliente: Optional[str], proyecto: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        if not cliente:
            return None, None
        registro = self.clientes.get_o_crear(cliente)
        if not proyecto:
            return registro.id, None
        return registro.id, self.proyectos.get_o_crear(proyecto, registro.id).id

    def _enriquecer(self, solicitud) -> SolicitudResponse:
        respuesta = SolicitudResponse.model_validate(solicitud)
        respuesta.criterios = [
            CriterioResponse.model_validate(c) for c in self.repo.listar_criterios(solicitud.id)
        ]

        if solicitud.cliente_id:
            cliente = self.clientes.get_by_id(solicitud.cliente_id)
            respuesta.cliente_nombre = cliente.nombre if cliente else None
        if solicitud.proyecto_id:
            proyecto = self.proyectos.get_by_id(solicitud.proyecto_id)
            respuesta.proyecto_nombre = proyecto.nombre if proyecto else None

        usuario = self.usuarios.get_by_id(solicitud.usuario_id)
        respuesta.usuario_nombre = usuario.nombre if usuario else None

        if solicitud.estado == ESTADO_PROCESADA:
            busqueda = self.busquedas.ultima_de_solicitud(solicitud.id)
            if busqueda:
                recomendaciones = self.busquedas.listar_recomendaciones(busqueda.id)
                respuesta.busqueda_id = busqueda.id
                respuesta.total_candidatos = len(recomendaciones)
                respuesta.mejor_afinidad = (
                    max(r.puntaje_afinidad for r in recomendaciones) if recomendaciones else None
                )

        return respuesta
