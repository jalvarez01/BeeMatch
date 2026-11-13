"""
Migración de los datos de SQLite (desarrollo) a PostgreSQL con pgvector.

Copia todas las tablas del esquema, en orden de dependencias, sin llamar al
servicio de IA: los embeddings que ya están en SQLite (guardados como JSON) se
convierten a columnas `vector`. Así no se paga de nuevo la indexación.

Uso:

    python -m scripts.migrar_sqlite_a_postgres \\
        --origen data/beematch.db \\
        --destino postgresql+psycopg://beematch:beematch@localhost:5432/beematch

Opciones:

    --vaciar       Borra el contenido de las tablas de destino antes de copiar.
                   Sin esta opción, si el destino ya tiene datos el script se
                   detiene sin tocar nada.
    --simular      Lee y valida el origen, pero no escribe en el destino.

Qué hace, en orden:
  1. Deja el destino con la extensión vector, las tablas, los índices HNSW y GIN
     y la versión de Alembic (los mismos pasos que la API al arrancar).
  2. Copia cada tabla en lotes. Solo pasan las columnas que existen en ambos
     lados, así que una base SQLite antigua (sin columnas nuevas) también sirve.
  3. Trata las referencias rotas. SQLite no hace cumplir las llaves foráneas,
     así que una base de desarrollo puede tener, por ejemplo, coincidencias que
     apuntan a un fragmento borrado al reindexar. PostgreSQL sí las exige: si la
     columna admite NULL la referencia se deja en NULL; si no, la fila se
     descarta. Ambos casos se informan.
  4. Compara el número de filas de cada tabla (descartadas incluidas) y termina
     con error si alguna no coincide. Toda la copia es una sola transacción: si
     algo falla, el destino queda como estaba.

El origen se abre en modo solo lectura: nunca se modifica.
"""

import argparse
import json
import os
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

LOTE = 500

# Referencias rotas que se corrigieron o filas que se descartaron, por motivo.
ajustes: Counter = Counter()
descartadas: Counter = Counter()


def _preparar_entorno(destino: str) -> None:
    # Los modelos eligen el tipo de la columna `embedding` al importarse, según
    # DATABASE_URL, así que debe apuntar al destino antes de importar `backend`.
    os.environ["DATABASE_URL"] = destino


def _convertir(valor, columna):
    """Adapta un valor leído de SQLite al tipo de la columna de PostgreSQL."""
    from pgvector.sqlalchemy import Vector
    from sqlalchemy import Boolean, DateTime

    if valor is None:
        return None
    tipo = columna.type
    if isinstance(tipo, Vector):
        return json.loads(valor) if isinstance(valor, str) else list(valor)
    if isinstance(tipo, DateTime) and isinstance(valor, str):
        fecha = datetime.fromisoformat(valor)
        # SQLite guardó UTC sin zona.
        return fecha if fecha.tzinfo else fecha.replace(tzinfo=UTC)
    if isinstance(tipo, Boolean):
        return bool(valor)
    return valor


def migrar(origen: Path, destino: str, vaciar: bool = False, simular: bool = False) -> dict[str, int]:
    _preparar_entorno(destino)

    from sqlalchemy import create_engine, func, inspect, select, text

    from backend.infrastructure.persistence import models  # noqa: F401  (registra las tablas)
    from backend.infrastructure.persistence.database import (
        Base,
        engine,
    )
    from backend.migraciones import actualizar_esquema

    if not origen.exists():
        raise SystemExit(f"No existe la base de origen: {origen}")
    if not destino.startswith("postgresql"):
        raise SystemExit("El destino debe ser una URL de PostgreSQL (postgresql+psycopg://...).")

    sqlite = create_engine(f"sqlite:///file:{origen.resolve()}?mode=ro&uri=true")
    tablas_origen = set(inspect(sqlite).get_table_names())

    if not simular:
        with engine.begin() as conexion:
            conexion.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        actualizar_esquema()  # tablas, índices y versión de Alembic

        with engine.connect() as conexion:
            ocupadas = [
                t.name
                for t in Base.metadata.sorted_tables
                if conexion.execute(select(func.count()).select_from(t)).scalar()
            ]
        if ocupadas and not vaciar:
            raise SystemExit(
                "El destino ya tiene datos en: " + ", ".join(ocupadas) + ". "
                "Usa --vaciar para reemplazarlos."
            )
        if ocupadas:
            with engine.begin() as conexion:
                for tabla in reversed(Base.metadata.sorted_tables):
                    conexion.execute(tabla.delete())

    copiadas: dict[str, int] = {}
    ajustes.clear()
    descartadas.clear()
    with sqlite.connect() as lectura, engine.begin() as escritura:
        ids_validos: dict[str, set] = {}
        for tabla in Base.metadata.sorted_tables:
            if tabla.name not in tablas_origen:
                copiadas[tabla.name] = 0
                continue
            columnas_origen = {c["name"] for c in inspect(sqlite).get_columns(tabla.name)}
            columnas = [c for c in tabla.columns if c.name in columnas_origen]
            nombres = ", ".join(c.name for c in columnas)
            filas = lectura.execute(text(f"SELECT {nombres} FROM {tabla.name}")).mappings()  # noqa: S608

            llaves = [
                (c, fk.column.table.name, fk.column.name)
                for c in columnas
                for fk in c.foreign_keys
            ]
            total = 0
            lote: list[dict] = []
            for fila in filas:
                nueva = {c.name: _convertir(fila[c.name], c) for c in columnas}
                descartar = False
                for columna, tabla_padre, columna_padre in llaves:
                    valor = nueva[columna.name]
                    if valor is None:
                        continue
                    if tabla_padre not in ids_validos:
                        padre = Base.metadata.tables[tabla_padre]
                        ids_validos[tabla_padre] = {
                            f[0]
                            for f in escritura.execute(select(padre.c[columna_padre])).fetchall()
                        }
                    if valor in ids_validos[tabla_padre]:
                        continue
                    clave = f"{tabla.name}.{columna.name} -> {tabla_padre}"
                    if columna.nullable:
                        nueva[columna.name] = None
                        ajustes[clave + " (referencia en NULL)"] += 1
                    else:
                        descartar = True
                        ajustes[clave + " (fila descartada)"] += 1
                        descartadas[tabla.name] += 1
                        break
                if descartar:
                    continue
                lote.append(nueva)
                if len(lote) >= LOTE:
                    total += _insertar(escritura, tabla, lote, simular)
                    lote = []
            total += _insertar(escritura, tabla, lote, simular)
            copiadas[tabla.name] = total
            ids_validos.pop(tabla.name, None)  # se recalcula con lo ya copiado

    if simular:
        return copiadas

    # Verificación: mismo número de filas en cada tabla.
    diferencias = []
    with sqlite.connect() as lectura, engine.connect() as escritura:
        for tabla in Base.metadata.sorted_tables:
            if tabla.name not in tablas_origen:
                continue
            en_origen = lectura.execute(text(f"SELECT COUNT(*) FROM {tabla.name}")).scalar()  # noqa: S608
            en_destino = escritura.execute(select(func.count()).select_from(tabla)).scalar()
            if en_origen - descartadas[tabla.name] != en_destino:
                diferencias.append(f"{tabla.name}: origen {en_origen}, destino {en_destino}")
    if diferencias:
        raise SystemExit("Las filas no coinciden:\n  " + "\n  ".join(diferencias))
    return copiadas


def _insertar(conexion, tabla, filas: list[dict], simular: bool) -> int:
    if not filas or simular:
        return len(filas)
    conexion.execute(tabla.insert(), filas)
    return len(filas)


def main() -> None:
    parser = argparse.ArgumentParser(description="Copia los datos de SQLite a PostgreSQL.")
    parser.add_argument("--origen", type=Path, default=Path("data/beematch.db"))
    parser.add_argument("--destino", required=True, help="URL de PostgreSQL (postgresql+psycopg://...)")
    parser.add_argument("--vaciar", action="store_true", help="Reemplaza lo que haya en el destino.")
    parser.add_argument("--simular", action="store_true", help="Solo lee el origen, no escribe.")
    argumentos = parser.parse_args()

    copiadas = migrar(argumentos.origen, argumentos.destino, argumentos.vaciar, argumentos.simular)

    verbo = "Se leerían" if argumentos.simular else "Se copiaron"
    print(f"{verbo} {sum(copiadas.values())} filas:")
    for nombre, cantidad in copiadas.items():
        if cantidad:
            print(f"  {nombre}: {cantidad}")
    if copiadas.get("configuracion_repositorio"):
        print(
            "AVISO: las credenciales del repositorio de hojas de vida van cifradas con la clave del\n"
            "  entorno de origen (ENCRYPTION_KEY o JWT_SECRET). Si el destino usa otra, no se podrán\n"
            "  descifrar: vuelve a registrarlas desde Configuración."
        )
    if ajustes:
        print("Referencias rotas en el origen (SQLite no las valida):")
        for motivo, cantidad in ajustes.items():
            print(f"  {motivo}: {cantidad}")
    if not argumentos.simular:
        print("Verificación correcta: el número de filas coincide en todas las tablas.")


if __name__ == "__main__":
    sys.exit(main())
