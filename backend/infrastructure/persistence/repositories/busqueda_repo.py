from typing import Optional

from sqlalchemy.orm import Session

from backend.infrastructure.persistence.models.busqueda import (
    BusquedaModel,
    CoincidenciaModel,
    PreseleccionModel,
    RecomendacionModel,
)


class BusquedaRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, busqueda_id: str) -> Optional[BusquedaModel]:
        return self.db.get(BusquedaModel, busqueda_id)

    def crear(self, solicitud_id: str) -> BusquedaModel:
        busqueda = BusquedaModel(solicitud_id=solicitud_id)
        self.db.add(busqueda)
        self.db.commit()
        self.db.refresh(busqueda)
        return busqueda

    def actualizar_progreso(self, busqueda_id: str, etapa: str, progreso: int) -> None:
        """Alimenta el indicador de progreso de la interfaz (HU-22, RNF25)."""
        busqueda = self.get_by_id(busqueda_id)
        if busqueda:
            busqueda.etapa = etapa
            busqueda.progreso = progreso
            self.db.commit()

    def finalizar(self, busqueda_id: str, **metricas) -> Optional[BusquedaModel]:
        busqueda = self.get_by_id(busqueda_id)
        if not busqueda:
            return None
        for clave, valor in metricas.items():
            if hasattr(busqueda, clave):
                setattr(busqueda, clave, valor)
        self.db.commit()
        self.db.refresh(busqueda)
        return busqueda

    def ultima_de_solicitud(self, solicitud_id: str) -> Optional[BusquedaModel]:
        return (
            self.db.query(BusquedaModel)
            .filter(BusquedaModel.solicitud_id == solicitud_id)
            .order_by(BusquedaModel.created_at.desc())
            .first()
        )

    # --- Recomendaciones y coincidencias -------------------------------------

    def guardar_recomendaciones(self, busqueda_id: str, recomendaciones: list[dict]) -> list[RecomendacionModel]:
        """
        Persiste el Top-N con su desglose. Cada coincidencia con evidencia debe
        traer fragmento_id (RD3).
        """
        creadas: list[RecomendacionModel] = []
        for posicion, datos in enumerate(recomendaciones, start=1):
            coincidencias = datos.pop("coincidencias", [])
            recomendacion = RecomendacionModel(busqueda_id=busqueda_id, posicion=posicion, **datos)
            self.db.add(recomendacion)
            self.db.flush()
            for c in coincidencias:
                self.db.add(CoincidenciaModel(recomendacion_id=recomendacion.id, **c))
            creadas.append(recomendacion)
        self.db.commit()
        return creadas

    def listar_recomendaciones(self, busqueda_id: str) -> list[RecomendacionModel]:
        return (
            self.db.query(RecomendacionModel)
            .filter(RecomendacionModel.busqueda_id == busqueda_id)
            .order_by(RecomendacionModel.posicion)
            .all()
        )

    def get_recomendacion(self, recomendacion_id: str) -> Optional[RecomendacionModel]:
        return self.db.get(RecomendacionModel, recomendacion_id)

    def listar_coincidencias(self, recomendacion_id: str) -> list[CoincidenciaModel]:
        return (
            self.db.query(CoincidenciaModel)
            .filter(CoincidenciaModel.recomendacion_id == recomendacion_id)
            .all()
        )

    def marcar_preseleccion(self, recomendacion_id: str, valor: bool) -> Optional[RecomendacionModel]:
        recomendacion = self.get_recomendacion(recomendacion_id)
        if not recomendacion:
            return None
        recomendacion.preseleccionado = valor
        self.db.commit()
        self.db.refresh(recomendacion)
        return recomendacion

    def registrar_preseleccion(self, busqueda_id: str, usuario_id: str, formato: str) -> PreseleccionModel:
        preseleccion = PreseleccionModel(
            busqueda_id=busqueda_id, usuario_id=usuario_id, formato_exportacion=formato
        )
        self.db.add(preseleccion)
        self.db.commit()
        self.db.refresh(preseleccion)
        return preseleccion
