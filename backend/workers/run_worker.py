"""
Arranque del worker de la cola (componente C17).

    python -m backend.workers.run_worker                  # solo procesa la cola
    python -m backend.workers.run_worker --planificador   # y además sincroniza cada N horas

El planificador (C18) debe correr en UN solo proceso. En el despliegue es el
worker, no la API, para que escalar la API a varias instancias no multiplique
las sincronizaciones (ver PLANIFICADOR_EN_API en config.py).

Se usa `SimpleWorker` y no el `rq worker` de la línea de comandos porque este
último hace `fork()` por cada trabajo, y en macOS el sistema mata el proceso
hijo ("objc ... fork() ... Crashing instead") en cuanto el trabajo toca una
librería de red. `SimpleWorker` ejecuta el trabajo en el mismo proceso, así que
el arranque es igual en macOS, Linux y Windows.

Los trabajos de este proyecto son cortos y no comparten estado, por lo que
perder el aislamiento del fork no afecta: si uno falla, RQ lo deja en la lista de
fallidos y el worker sigue con el siguiente.
"""

import argparse
import logging
import os

from redis import Redis
from rq import Queue, SimpleWorker

from backend.config import REDIS_URL

NOMBRE_COLA = "beematch"


def main() -> None:
    parser = argparse.ArgumentParser(description="Worker de la cola de trabajos de BeeMatch.")
    parser.add_argument(
        "--planificador",
        action="store_true",
        help="Además de procesar la cola, sincroniza el repositorio cada SYNC_INTERVALO_HORAS.",
    )
    argumentos = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    conexion = Redis.from_url(REDIS_URL)

    if argumentos.planificador:
        from backend.workers.scheduler import iniciar_planificador

        if iniciar_planificador() is None:
            logging.getLogger(__name__).warning("APScheduler no está instalado: sin planificador.")
        else:
            logging.getLogger(__name__).info("Planificador activo en este worker.")

    opciones = {}
    if os.name == "nt":
        # Windows no tiene SIGALRM, que es con lo que RQ corta un trabajo vencido.
        from rq.timeouts import TimerDeathPenalty

        opciones["death_penalty_class"] = TimerDeathPenalty

    worker = SimpleWorker([Queue(NOMBRE_COLA, connection=conexion)], connection=conexion, **opciones)
    worker.work()


if __name__ == "__main__":
    main()
