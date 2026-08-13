"""Métricas de la pantalla de inicio."""

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from backend.infrastructure.persistence.models.hoja_vida import ESTADO_INDEXADA
from backend.infrastructure.persistence.models.solicitud import (
    ESTADO_BORRADOR,
    ESTADO_EN_ANALISIS,
    ESTADO_PROCESADA,
)
from backend.infrastructure.persistence.repositories.busqueda_repo import BusquedaRepository
from backend.infrastructure.persistence.repositories.candidato_repo import CandidatoRepository
from backend.infrastructure.persistence.repositories.cliente_repo import ClienteRepository
from backend.infrastructure.persistence.repositories.hoja_vida_repo import HojaDeVidaRepository
from backend.infrastructure.persistence.repositories.solicitud_repo import SolicitudRepository
from backend.schemas.dashboard import DashboardResponse, SolicitudRecienteResponse


class DashboardService:
    def __init__(self, db: Session):
        self.db = db
        self.solicitudes = SolicitudRepository(db)
        self.busquedas = BusquedaRepository(db)
        self.hojas = HojaDeVidaRepository(db)
        self.candidatos = CandidatoRepository(db)
        self.clientes = ClienteRepository(db)

    def resumen(self) -> DashboardResponse:
        recientes = self.solicitudes.listar(limite=5)

        puntajes: list[float] = []
        alta_afinidad = 0
        sin_coincidencias = 0
        recomendadas = 0

        for solicitud in self.solicitudes.listar(limite=50):
            busqueda = self.busquedas.ultima_de_solicitud(solicitud.id)
            if not busqueda:
                continue
            recomendaciones = self.busquedas.listar_recomendaciones(busqueda.id)
            if not recomendaciones and solicitud.estado == ESTADO_PROCESADA:
                sin_coincidencias += 1
            recomendadas += len(recomendaciones)
            for r in recomendaciones:
                puntajes.append(r.puntaje_afinidad)
                if r.nivel == "ALTA":
                    alta_afinidad += 1

        return DashboardResponse(
            solicitudes_activas=self.solicitudes.contar(ESTADO_EN_ANALISIS)
            + self.solicitudes.contar(ESTADO_BORRADOR),
            perfiles_recomendados=recomendadas,
            hojas_vida_analizadas=self.hojas.contar_por_estado(ESTADO_INDEXADA),
            afinidad_promedio=round(sum(puntajes) / len(puntajes), 1) if puntajes else 0.0,
            candidatos_alta_afinidad=alta_afinidad,
            perfiles_nuevos=self.candidatos.contar(),
            solicitudes_sin_coincidencias=sin_coincidencias,
            recientes=[self._reciente(s) for s in recientes],
        )

    def _reciente(self, solicitud) -> SolicitudRecienteResponse:
        cliente = self.clientes.get_by_id(solicitud.cliente_id) if solicitud.cliente_id else None
        return SolicitudRecienteResponse(
            id=solicitud.id,
            perfil=solicitud.rol_buscado or "Sin rol definido",
            cliente=cliente.nombre if cliente else None,
            estado=solicitud.estado,
            hace=self._tiempo_relativo(solicitud.created_at),
        )

    @staticmethod
    def _tiempo_relativo(fecha) -> str:
        if not fecha:
            return ""
        if fecha.tzinfo is None:
            fecha = fecha.replace(tzinfo=timezone.utc)
        delta = datetime.now(timezone.utc) - fecha
        horas = int(delta.total_seconds() // 3600)
        if horas < 1:
            return "hace unos minutos"
        if horas < 24:
            return f"hace {horas} horas"
        dias = horas // 24
        return "ayer" if dias == 1 else f"hace {dias} días"
