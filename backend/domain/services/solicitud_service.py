"""Gestión de solicitudes de staffing (HU-08 a HU-15)."""

from typing import Optional

from sqlalchemy.orm import Session

from backend.infrastructure.persistence.models.solicitud import (
    ESTADO_BORRADOR,
    ESTADO_EN_ANALISIS,
    ESTADO_ERROR,
    ESTADO_PROCESADA,
    ESTADO_SIN_COINCIDENCIAS,
)
from backend.infrastructure.persistence.repositories.busqueda_repo import BusquedaRepository
from backend.infrastructure.persistence.repositories.cliente_repo import (
    ClienteRepository,
    ProyectoRepository,
)
from backend.infrastructure.persistence.repositories.solicitud_repo import SolicitudRepository
from backend.infrastructure.persistence.repositories.usuario_repo import UsuarioRepository
from backend.schemas.solicitud import (
    DESCRIPCION_MIN_CARACTERES,
    AjusteSolicitud,
    CriterioResponse,
    SolicitudCreate,
    SolicitudResponse,
    SolicitudUpdate,
)

MENSAJE_DESCRIPCION_CORTA = (
    "La descripción es muy corta. Describe el perfil con más detalle "
    f"(mínimo {DESCRIPCION_MIN_CARACTERES} caracteres)."
)


CAMPO_DESCRIPCION = "descripción del perfil"
CAMPO_ROL = "rol requerido"
CAMPO_CLIENTE = "cliente"

# HU-12: toda solicitud pertenece a un cliente, para saber qué proyecto de Staff
# Augmentation originó la búsqueda.
MENSAJE_CLIENTE_OBLIGATORIO = "Indica el cliente que originó la solicitud."


def descripcion_insuficiente(descripcion: Optional[str]) -> bool:
    """
    HU-08: un texto libre que se escribió pero quedó por debajo del mínimo no le
    da contexto suficiente al servicio de IA.

    El texto vacío no entra aquí: lo resuelve la validación de campos
    obligatorios (HU-10, `campos_faltantes`).
    """
    texto = (descripcion or "").strip()
    return 0 < len(texto) < DESCRIPCION_MIN_CARACTERES


def campos_faltantes(descripcion: Optional[str], rol: Optional[str]) -> list[str]:
    """
    HU-10: sin rol o sin descripción del perfil la búsqueda daría resultados
    poco útiles, así que no se ejecuta. Devuelve los campos que faltan, en el
    orden en que aparecen en el formulario.
    """
    faltantes = []
    if not (descripcion or "").strip():
        faltantes.append(CAMPO_DESCRIPCION)
    if not (rol or "").strip():
        faltantes.append(CAMPO_ROL)
    return faltantes


def cliente_en_blanco(cliente: Optional[str]) -> bool:
    """HU-12: ¿falta el cliente? Un texto de solo espacios cuenta como vacío."""
    return not (cliente or "").strip()


def campos_faltantes_busqueda(
    descripcion: Optional[str], rol: Optional[str], cliente: Optional[str]
) -> list[str]:
    """
    HU-10 y HU-12: lo que falta para poder ejecutar una búsqueda, en el orden del
    formulario (descripción, cliente, rol).
    """
    faltantes = []
    if not (descripcion or "").strip():
        faltantes.append(CAMPO_DESCRIPCION)
    if cliente_en_blanco(cliente):
        faltantes.append(CAMPO_CLIENTE)
    if not (rol or "").strip():
        faltantes.append(CAMPO_ROL)
    return faltantes


def mensaje_campos_faltantes(faltantes: list[str]) -> str:
    return f"Completa la información obligatoria para buscar: {' y '.join(faltantes)}."


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
        Actualización parcial: lo que no llega se conserva. Editar una solicitud
        procesada no borra sus ejecuciones anteriores (HU-15, RD1): cada una guarda
        su propia copia de los criterios.
        """
        solicitud = self.repo.get_by_id(solicitud_id)
        if not solicitud:
            return None

        self.repo.actualizar(
            solicitud,
            descripcion_libre=datos.descripcion_libre,
            rol_buscado=datos.rol_buscado,
            experiencia_min=datos.experiencia_min,
        )
        self._actualizar_cliente(solicitud, datos.cliente, datos.proyecto)
        if datos.criterios is not None:
            self.repo.reemplazar_criterios(solicitud.id, [c.model_dump() for c in datos.criterios])
        return self._enriquecer(solicitud)

    def reemplazar(self, solicitud_id: str, datos: AjusteSolicitud) -> Optional[SolicitudResponse]:
        """
        HU-15: la solicitud queda exactamente con los criterios ajustados, incluidos
        los que se quitaron (experiencia mínima, tecnologías). No toca las ejecuciones
        anteriores: ellas conservan la copia de lo que analizaron.
        """
        solicitud = self.repo.get_by_id(solicitud_id)
        if not solicitud:
            return None

        cliente_id, proyecto_id = self._resolver_cliente(datos.cliente, datos.proyecto)
        self.repo.reemplazar(
            solicitud,
            descripcion_libre=datos.descripcion_libre,
            rol_buscado=datos.rol_buscado,
            experiencia_min=datos.experiencia_min,
            cliente_id=cliente_id,
            proyecto_id=proyecto_id,
        )
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

    def eliminar_borrador(self, solicitud_id: str) -> bool:
        solicitud = self.repo.get_by_id(solicitud_id)
        if not solicitud:
            return False
        if solicitud.estado != ESTADO_BORRADOR:
            raise ValueError("Solo se pueden eliminar solicitudes en estado Borrador.")
        self.repo.eliminar_borrador(solicitud)
        return True

    def obtener(self, solicitud_id: str) -> Optional[SolicitudResponse]:
        solicitud = self.repo.get_by_id(solicitud_id)
        return self._enriquecer(solicitud) if solicitud else None

    def historial(
        self,
        estado: Optional[str] = None,
        texto: Optional[str] = None,
        pagina: int = 1,
        por_pagina: int = 10,
        cliente_id: Optional[str] = None,
    ) -> tuple[list[SolicitudResponse], int]:
        """HU-13: historial filtrable y paginado. HU-12: también por cliente."""
        solicitudes = self.repo.listar(
            estado=estado,
            texto=texto,
            limite=por_pagina,
            desplazamiento=(pagina - 1) * por_pagina,
            cliente_id=cliente_id,
        )
        total = self.repo.contar(estado=estado, texto=texto, cliente_id=cliente_id)
        return [self._enriquecer(s) for s in solicitudes], total

    # --- Internos ------------------------------------------------------------

    def _resolver_cliente(
        self, cliente: Optional[str], proyecto: Optional[str]
    ) -> tuple[Optional[str], Optional[str]]:
        """
        HU-12: ids del cliente y del proyecto, registrándolos si no existen. Los
        nombres que solo difieren en mayúsculas o espacios son el mismo registro.
        """
        if cliente_en_blanco(cliente):
            return None, None
        registro = self.clientes.get_o_crear(cliente or "")
        if not (proyecto or "").strip():
            return registro.id, None
        return registro.id, self.proyectos.get_o_crear(proyecto or "", registro.id).id

    def _actualizar_cliente(
        self, solicitud, cliente: Optional[str], proyecto: Optional[str]
    ) -> None:
        """
        Actualización parcial de cliente y proyecto: lo que no llega se conserva.
        Si cambia el cliente, el proyecto anterior (que era de otro cliente) se descarta
        salvo que llegue uno nuevo.
        """
        if cliente is None and proyecto is None:
            return

        cliente_id = solicitud.cliente_id
        if not cliente_en_blanco(cliente):
            cliente_id = self.clientes.get_o_crear(cliente or "").id

        if proyecto is None:
            proyecto_id = solicitud.proyecto_id if cliente_id == solicitud.cliente_id else None
        elif proyecto.strip() and cliente_id:
            proyecto_id = self.proyectos.get_o_crear(proyecto, cliente_id).id
        else:
            proyecto_id = None

        self.repo.asociar_cliente(solicitud, cliente_id, proyecto_id)

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

        respuesta.total_ejecuciones = self.busquedas.contar_de_solicitud(solicitud.id)

        # HU-23: una solicitud sin coincidencias también tiene búsqueda, para
        # poder abrir sus resultados desde el historial.
        if solicitud.estado in (ESTADO_PROCESADA, ESTADO_SIN_COINCIDENCIAS):
            busqueda = self.busquedas.ultima_de_solicitud(solicitud.id)
            if busqueda:
                recomendaciones = self.busquedas.listar_recomendaciones(busqueda.id)
                respuesta.busqueda_id = busqueda.id
                respuesta.total_candidatos = len(recomendaciones)
                respuesta.mejor_afinidad = (
                    max(r.puntaje_afinidad for r in recomendaciones) if recomendaciones else None
                )
                respuesta.total_preseleccionados = sum(1 for r in recomendaciones if r.preseleccionado)
        elif solicitud.estado in (ESTADO_EN_ANALISIS, ESTADO_ERROR):
            # HU-15: una ejecución en curso o fallida también se puede abrir desde el
            # historial, y desde ahí se llega a las ejecuciones anteriores con resultados.
            busqueda = self.busquedas.ultima_de_solicitud(solicitud.id)
            respuesta.busqueda_id = busqueda.id if busqueda else None

        return respuesta
