import type { BusquedaEstado, BusquedaResultado, Recomendacion } from '../types'
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

export async function marcarPreseleccion(
  recomendacionId: string,
  preseleccionado: boolean,
): Promise<Recomendacion> {
  return apiFetch<Recomendacion>(`/busquedas/recomendacion/${recomendacionId}/preseleccion`, {
    method: 'PATCH',
    body: JSON.stringify({ preseleccionado }),
  })
}

/** Sondea el estado hasta que la búsqueda termina. Alimenta la barra de progreso. */
export async function esperarResultado(
  busquedaId: string,
  alProgresar: (estado: BusquedaEstado) => void,
  intervaloMs = 2000,
): Promise<BusquedaResultado> {
  for (;;) {
    const estado = await consultarEstado(busquedaId)
    alProgresar(estado)

    if (estado.estado === 'COMPLETADA') return obtenerResultados(busquedaId)
    if (estado.estado === 'ERROR') {
      throw new Error(estado.mensaje_error || 'La búsqueda no pudo completarse.')
    }

    await new Promise((r) => setTimeout(r, intervaloMs))
  }
}
