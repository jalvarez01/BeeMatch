import type { Rol } from '../types'
import { apiFetch } from './client'

/** HU-06: consulta de la bitácora de actividad (solo administración). */

export interface EventoBitacora {
  id: string
  created_at: string | null
  usuario_id: string | null
  usuario_nombre: string | null
  usuario_correo: string | null
  rol: Rol | null
  accion: string
  entidad: string | null
  entidad_id: string | null
  detalle: string | null
}

export interface PaginaBitacora {
  total: number
  limite: number
  desplazamiento: number
  items: EventoBitacora[]
}

export interface FiltrosBitacora {
  usuarioId?: string
  fechaDesde?: string
  fechaHasta?: string
  limite: number
  desplazamiento: number
}

export async function consultarBitacora(
  filtros: FiltrosBitacora,
): Promise<PaginaBitacora> {
  const parametros = new URLSearchParams({
    limite: String(filtros.limite),
    desplazamiento: String(filtros.desplazamiento),
  })
  if (filtros.usuarioId) parametros.set('usuario_id', filtros.usuarioId)
  if (filtros.fechaDesde) parametros.set('fecha_desde', filtros.fechaDesde)
  if (filtros.fechaHasta) parametros.set('fecha_hasta', filtros.fechaHasta)

  return apiFetch<PaginaBitacora>(`/configuracion/bitacora?${parametros}`)
}
