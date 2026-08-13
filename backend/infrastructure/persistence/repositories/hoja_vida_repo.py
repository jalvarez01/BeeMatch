from typing import Optional

from sqlalchemy.orm import Session

from backend.infrastructure.persistence.models._base import utcnow
from backend.infrastructure.persistence.models.hoja_vida import (
    CandidatoModel,
    FragmentoCVModel,
    HojaDeVidaModel,
)
from backend.infrastructure.persistence.models.hoja_vida import (
    ESTADO_INDEXADA,
    ESTADO_NO_PROCESABLE,
    ESTADO_PENDIENTE,
)


class HojaDeVidaRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, hoja_id: str) -> Optional[HojaDeVidaModel]:
        return self.db.get(HojaDeVidaModel, hoja_id)

    def get_by_onedrive_id(self, id_onedrive: str) -> Optional[HojaDeVidaModel]:
        return (
            self.db.query(HojaDeVidaModel)
            .filter(HojaDeVidaModel.id_onedrive == id_onedrive)
            .first()
        )

    def registrar_o_actualizar(self, datos: dict) -> tuple[HojaDeVidaModel, bool]:
        """
        Alta o actualización desde la sincronización con OneDrive.
        Retorna (hoja, necesita_reindexar). RD5: solo se reindexa si cambió.
        """
        existente = self.get_by_onedrive_id(datos["id_onedrive"])
        if not existente:
            hoja = HojaDeVidaModel(**datos)
            self.db.add(hoja)
            self.db.commit()
            self.db.refresh(hoja)
            return hoja, True

        cambio = (
            existente.hash_contenido != datos.get("hash_contenido")
            or existente.fecha_modificacion != datos.get("fecha_modificacion")
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

    def contar_por_estado(self, estado: str) -> int:
        return (
            self.db.query(HojaDeVidaModel)
            .filter(HojaDeVidaModel.estado_procesamiento == estado)
            .count()
        )

    def eliminar_indice(self, hoja_id: str) -> None:
        """RNF16: derecho de supresión. Borra fragmentos y candidato derivados."""
        self.db.query(FragmentoCVModel).filter(FragmentoCVModel.hoja_de_vida_id == hoja_id).delete()
        self.db.query(CandidatoModel).filter(CandidatoModel.hoja_de_vida_id == hoja_id).delete()
        self.db.commit()
