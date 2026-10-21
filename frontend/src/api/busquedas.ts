import type {
  BusquedaEstado,
  BusquedaResultado,
  DisponibilidadHojaVida,
  Recomendacion,
} from '../types'
import { apiFetch } from './client'

export async function ejecutarBusqueda(solicitudId: string): Promise<BusquedaEstado> {
  return apiFetch<BusquedaEstado>(`/busquedas/solicitud/${solicitudId}`, { method: 'POST' })
}

export async function consultarEstado(busquedaId: string): Promise<BusquedaEstado> {
  return apiFetch<BusquedaEstado>(`/busquedas/${busquedaId}/estado`)
}

export async function obtenerResultados(busquedaId: string): Promise<BusquedaResultado> {
  return apiFetch<BusquedaResultado>(`/busquedas/${busquedaId}`)
}

export async function obtenerRecomendacion(recomendacionId: string): Promise<Recomendacion> {
  return apiFetch<Recomendacion>(`/busquedas/recomendacion/${recomendacionId}`)
}

/** HU-21: consulta al repositorio si la hoja de vida sigue disponible. */
export async function consultarHojaDeVida(recomendacionId: string): Promise<DisponibilidadHojaVida> {
  return apiFetch<DisponibilidadHojaVida>(`/busquedas/recomendacion/${recomendacionId}/hoja-de-vida`)
}

export async function marcarPreseleccion(
  recomendacionId: string,
  preseleccionado: boolean,
): Promise<Recomendacion> {
  return apiFetch<Recomendacion>(`/busquedas/recomendacion/${recomendacionId}/preseleccion`, {
    method: 'PATCH',
    body: JSON.stringify({ preseleccionado }),
  })
}

/** HU-22: tiempo máximo que la pantalla espera antes de dejar de sondear. */
export const TIEMPO_MAXIMO_ESPERA_MS = 180_000

export const MENSAJE_ESPERA_AGOTADA =
  'El análisis está tardando más de lo habitual y sigue en curso. Consulta el historial en unos minutos para ver el resultado.'

/** Texto del indicador según el estado, cuando el servidor aún no informa una etapa. */
export function etapaPorDefecto(estado: BusquedaEstado['estado']): string {
  return estado === 'EN_COLA' ? 'Pendiente: esperando para iniciar' : 'Analizando'
}

export function esperaCancelada(e: unknown): boolean {
  return e instanceof DOMException && e.name === 'AbortError'
}

interface OpcionesEspera {
  intervaloMs?: number
  /** Pasado este tiempo se deja de esperar. El análisis en el servidor sigue su curso. */
  tiempoMaximoMs?: number
  /** Al abortar se deja de sondear (por ejemplo, cuando la persona sale de la pantalla). */
  signal?: AbortSignal
}

/**
 * Sondea el estado hasta que la búsqueda termina. Alimenta la barra de progreso.
 *
 * Termina con error si la búsqueda falla o si se agota el tiempo máximo, y con
 * AbortError si se cancela con `signal`: sin eso el sondeo seguía cada dos
 * segundos aunque la persona ya hubiera cambiado de pantalla.
 */
export async function esperarResultado(
  busquedaId: string,
  alProgresar: (estado: BusquedaEstado) => void,
  { intervaloMs = 2000, tiempoMaximoMs = TIEMPO_MAXIMO_ESPERA_MS, signal }: OpcionesEspera = {},
): Promise<BusquedaResultado> {
  const limite = Date.now() + tiempoMaximoMs

  for (;;) {
    signal?.throwIfAborted()

    const estado = await consultarEstado(busquedaId)
    signal?.throwIfAborted()
    alProgresar(estado)

    if (estado.estado === 'COMPLETADA') return obtenerResultados(busquedaId)
    if (estado.estado === 'ERROR') {
      throw new Error(estado.mensaje_error || 'La búsqueda no pudo completarse.')
    }
    if (Date.now() + intervaloMs > limite) throw new Error(MENSAJE_ESPERA_AGOTADA)

    await pausa(intervaloMs, signal)
  }
}

function pausa(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolver, rechazar) => {
    const temporizador = setTimeout(() => {
      signal?.removeEventListener('abort', cancelar)
      resolver()
    }, ms)
    const cancelar = () => {
      clearTimeout(temporizador)
      rechazar(new DOMException('Espera cancelada', 'AbortError'))
    }
    signal?.addEventListener('abort', cancelar, { once: true })
  })
}
