from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from backend.infrastructure.persistence.models._base import utcnow
from backend.infrastructure.persistence.models.hoja_vida import (
    CandidatoHabilidadModel,
    CandidatoModel,
    FragmentoCVModel,
    HojaDeVidaModel,
)
from backend.infrastructure.persistence.models.hoja_vida import (
    ESTADO_INDEXADA,
    ESTADO_NO_PROCESABLE,
    ESTADO_PENDIENTE,
)


def _misma_fecha(guardada: Optional[datetime], entrante: Optional[datetime]) -> bool:
    """
    Compara dos fechas de modificación sin que la zona horaria las separe.

    El proveedor las entrega con zona (UTC) y SQLite las devuelve sin ella,
    porque no guarda el huso. Comparadas tal cual, un datetime naive y uno
    aware nunca son iguales: toda hoja parecería modificada en cada
    sincronización y el repositorio entero se reindexaría cada vez, con su
    costo en llamadas al modelo. Todo el proyecto trabaja en UTC (`utcnow`),
    así que una fecha sin zona se interpreta como UTC.
    """
    if guardada is None or entrante is None:
        return guardada is None and entrante is None
    if guardada.tzinfo is None:
        guardada = guardada.replace(tzinfo=timezone.utc)
    if entrante.tzinfo is None:
        entrante = entrante.replace(tzinfo=timezone.utc)
    return guardada == entrante


class HojaDeVidaRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, hoja_id: str) -> Optional[HojaDeVidaModel]:
        return self.db.get(HojaDeVidaModel, hoja_id)

    def get_by_id_documento(self, id_documento: str) -> Optional[HojaDeVidaModel]:
        return (
            self.db.query(HojaDeVidaModel)
            .filter(HojaDeVidaModel.id_documento == id_documento)
            .first()
        )

    def registrar_o_actualizar(self, datos: dict) -> tuple[HojaDeVidaModel, bool]:
        """
        Alta o actualización desde la sincronización con el repositorio.
        Retorna (hoja, necesita_reindexar). RD5: solo se reindexa si cambió.
        """
        existente = self.get_by_id_documento(datos["id_documento"])
        if not existente:
            hoja = HojaDeVidaModel(**datos)
            self.db.add(hoja)
            self.db.commit()
            self.db.refresh(hoja)
            return hoja, True

        cambio = existente.hash_contenido != datos.get("hash_contenido") or not _misma_fecha(
            existente.fecha_modificacion, datos.get("fecha_modificacion")
        )
        for clave, valor in datos.items():
            setattr(existente, clave, valor)
        if cambio:
            existente.estado_procesamiento = ESTADO_PENDIENTE
        self.db.commit()
        self.db.refresh(existente)
        return existente, cambio

    def marcar_indexada(self, hoja_id: str) -> None:
        hoja = self.get_by_id(hoja_id)
        if hoja:
            hoja.estado_procesamiento = ESTADO_INDEXADA
            hoja.motivo_error = None
            hoja.indexada_en = utcnow()
            self.db.commit()

    def marcar_no_procesable(self, hoja_id: str, motivo: str) -> None:
        """RNF19: el documento que falla se registra, no aborta el proceso."""
        hoja = self.get_by_id(hoja_id)
        if hoja:
            hoja.estado_procesamiento = ESTADO_NO_PROCESABLE
            hoja.motivo_error = motivo
            self.db.commit()

    def listar_pendientes(self) -> list[HojaDeVidaModel]:
        return (
            self.db.query(HojaDeVidaModel)
            .filter(HojaDeVidaModel.estado_procesamiento == ESTADO_PENDIENTE)
            .all()
        )

    def listar_por_estado(self, estado: str) -> list[HojaDeVidaModel]:
        return (
            self.db.query(HojaDeVidaModel)
            .filter(HojaDeVidaModel.estado_procesamiento == estado)
            .order_by(HojaDeVidaModel.nombre_archivo)
            .all()
        )

    def contar_por_estado(self, estado: str) -> int:
        return (
            self.db.query(HojaDeVidaModel)
            .filter(HojaDeVidaModel.estado_procesamiento == estado)
            .count()
        )

    def eliminar_indice(self, hoja_id: str) -> None:
        """RNF16: derecho de supresión. Borra fragmentos y candidato derivados."""
        self.db.query(FragmentoCVModel).filter(FragmentoCVModel.hoja_de_vida_id == hoja_id).delete()
        # Las habilidades cuelgan del candidato, no de la hoja: si no se borran
        # aquí quedan huérfanas y la tabla crece con filas que no apuntan a nadie.
        candidatos = [
            c.id
            for c in self.db.query(CandidatoModel.id)
            .filter(CandidatoModel.hoja_de_vida_id == hoja_id)
            .all()
        ]
        if candidatos:
            self.db.query(CandidatoHabilidadModel).filter(
                CandidatoHabilidadModel.candidato_id.in_(candidatos)
            ).delete(synchronize_session=False)
        self.db.query(CandidatoModel).filter(CandidatoModel.hoja_de_vida_id == hoja_id).delete()
        self.db.commit()

    def listar_ausentes(self, id_documentos_presentes: set[str]) -> list[HojaDeVidaModel]:
        """Hojas de vida cuyo documento ya no aparece en el listado del origen."""
        return [
            hoja
            for hoja in self.db.query(HojaDeVidaModel).all()
            if hoja.id_documento not in id_documentos_presentes
        ]

    def eliminar(self, hoja_id: str) -> None:
        """Borra la referencia al documento. Lo derivado se quita con eliminar_indice."""
        self.db.query(HojaDeVidaModel).filter(HojaDeVidaModel.id == hoja_id).delete()
        self.db.commit()
