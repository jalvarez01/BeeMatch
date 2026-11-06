/**
 * HU-15 y HU-22: evita que una acción se lance dos veces mientras la primera sigue en curso.
 *
 * Deshabilitar el botón desde el estado de React no basta: entre dos clics muy seguidos
 * la pantalla aún no se volvió a pintar y el segundo clic llega con el botón activo. Esta
 * guarda se marca de forma síncrona, antes del primer `await`.
 */
export interface GuardaEnvio {
  readonly activo: boolean
  /** Ejecuta la tarea, o devuelve `undefined` sin ejecutarla si ya hay una en curso. */
  ejecutar: <T>(tarea: () => Promise<T>) => Promise<T | undefined>
}

export function crearGuardaEnvio(): GuardaEnvio {
  let activo = false
  return {
    get activo() {
      return activo
    },
    async ejecutar<T>(tarea: () => Promise<T>): Promise<T | undefined> {
      if (activo) return undefined
      activo = true
      try {
        return await tarea()
      } finally {
        activo = false
      }
    },
  }
}
