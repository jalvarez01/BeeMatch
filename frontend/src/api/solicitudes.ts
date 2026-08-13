import type { Historial, Solicitud, SolicitudPayload } from '../types'
import { apiFetch } from './client'

export async function crearSolicitud(datos: SolicitudPayload): Promise<Solicitud> {
  return apiFetch<Solicitud>('/solicitudes/', {
    method: 'POST',
    body: JSON.stringify(datos),
  })
}

export async function actualizarSolicitud(
  id: string,
  datos: Partial<SolicitudPayload>,
): Promise<Solicitud> {
  return apiFetch<Solicitud>(`/solicitudes/${id}`, {
    method: 'PUT',
    body: JSON.stringify(datos),
  })
}

export async function obtenerSolicitud(id: string): Promise<Solicitud> {
  return apiFetch<Solicitud>(`/solicitudes/${id}`)
}

export async function duplicarSolicitud(id: string): Promise<Solicitud> {
  return apiFetch<Solicitud>(`/solicitudes/${id}/duplicar`, { method: 'POST' })
}

export async function listarHistorial(params: {
  estado?: string
  texto?: string
  pagina?: number
}): Promise<Historial> {
  const query = new URLSearchParams()
  if (params.estado) query.set('estado', params.estado)
  if (params.texto) query.set('texto', params.texto)
  query.set('pagina', String(params.pagina ?? 1))
  return apiFetch<Historial>(`/solicitudes/?${query.toString()}`)
}
