"""
Reindexación de las hojas de vida que se indexaron antes de que existiera la
extracción del perfil con IA (RF02, HU-18).

Por qué hace falta: el perfil estructurado —rol, años, ubicación y tecnologías—
se extrae dentro de `IndexacionService.indexar_hoja`, y esa función sale
temprano si la hoja ya está INDEXADA. La sincronización, por su parte, solo
reencola lo que cambió en el origen o quedó PENDIENTE. Resultado: un documento
indexado antes de HU-18 se queda sin perfil para siempre, y su tarjeta de
resultados aparece sin rol ni tecnologías. Este script lo destraba.

El proyecto no usa Alembic, así que esta puesta al día es un script, igual que
`migrar_configuracion_repositorio`. Es idempotente: por defecto solo toca las
hojas cuyo candidato no tiene perfil, de modo que correrlo dos veces no gasta
llamadas al modelo de más.

Cuesta dinero: cada hoja son sus embeddings más una llamada al modelo. Sobre 30
CVs son unos pocos minutos.

Uso normal (solo las que les falta el perfil):

    python -m scripts.reindexar_perfiles

Forzar todas, por ejemplo después de cambiar el prompt de extracción:

    python -m scripts.reindexar_perfiles --todas

Probar con unas pocas antes de soltar el lote entero:

    python -m scripts.reindexar_perfiles --limite 3
"""

import sys
import time

from backend.infrastructure.persistence import models  # noqa: F401  (registra las tablas)
from backend.infrastructure.persistence.database import SessionLocal
from backend.infrastructure.persistence.models.hoja_vida import (
    CandidatoModel,
    ESTADO_INDEXADA,
    ESTADO_PENDIENTE,
    HojaDeVidaModel,
)
from backend.workers.ingesta_worker import indexar_hoja_de_vida


def _argumento_entero(bandera: str) -> int | None:
    if bandera not in sys.argv:
        return None
    posicion = sys.argv.index(bandera) + 1
    if posicion >= len(sys.argv):
        raise SystemExit(f"Falta el número después de {bandera}.")
    return int(sys.argv[posicion])


def hojas_a_reindexar(db, todas: bool, limite: int | None) -> list[tuple[str, str]]:
    """
    Hojas indexadas que hay que volver a procesar.

    Sin `--todas`, solo las que no tienen perfil: su candidato no existe todavía
    o quedó sin rol, que es la señal de que se indexaron antes de HU-18.
    """
    consulta = (
        db.query(HojaDeVidaModel)
        .outerjoin(CandidatoModel, CandidatoModel.hoja_de_vida_id == HojaDeVidaModel.id)
        .filter(HojaDeVidaModel.estado_procesamiento == ESTADO_INDEXADA)
    )
    if not todas:
        consulta = consulta.filter(
            (CandidatoModel.id.is_(None)) | (CandidatoModel.rol_principal.is_(None))
        )

    consulta = consulta.order_by(HojaDeVidaModel.nombre_archivo)
    hojas = consulta.limit(limite).all() if limite else consulta.all()
    return [(h.id, h.nombre_archivo) for h in hojas]


def main() -> int:
    todas = "--todas" in sys.argv
    limite = _argumento_entero("--limite")

    db = SessionLocal()
    try:
        pendientes = hojas_a_reindexar(db, todas, limite)
        if not pendientes:
            print("No hay hojas de vida sin perfil: nada que reindexar.")
            print("Para rehacerlas igual (por ejemplo, tras cambiar el prompt): --todas")
            return 0

        print(f"A reindexar: {len(pendientes)} hoja(s) de vida.")
        # Vuelven a PENDIENTE para que `indexar_hoja` no las salte por estar
        # ya indexadas.
        for hoja_id, _ in pendientes:
            db.get(HojaDeVidaModel, hoja_id).estado_procesamiento = ESTADO_PENDIENTE
        db.commit()
    finally:
        db.close()

    indexadas = fallidas = 0
    for numero, (hoja_id, nombre) in enumerate(pendientes, start=1):
        inicio = time.monotonic()
        try:
            exito = indexar_hoja_de_vida(hoja_id)
        except Exception as exc:  # noqa: BLE001  (un documento no puede tumbar el lote)
            exito = False
            print(f"  [{numero}/{len(pendientes)}] {nombre[:50]:50} ERROR {type(exc).__name__}: {exc}")
        else:
            estado = "ok" if exito else "no procesable"
            print(
                f"  [{numero}/{len(pendientes)}] {nombre[:50]:50} "
                f"{estado} ({time.monotonic() - inicio:.1f}s)"
            )
        indexadas += exito
        fallidas += not exito

    print(f"\nIndexadas: {indexadas} | sin indexar: {fallidas}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
