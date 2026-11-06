import type { ClienteSugerido } from '../types'
import { apiFetch } from './client'

/**
 * HU-12: clientes ya registrados cuyo nombre empieza por `texto`. Sin texto lista
 * los primeros por orden alfabético (con `limite` alto, alimenta el filtro del historial).
 */
export async function listarClientes(
  texto = '',
  limite = 8,
  signal?: AbortSignal,
): Promise<ClienteSugerido[]> {
  const query = new URLSearchParams({ limite: String(limite) })
  if (texto.trim()) query.set('q', texto.trim())
  return apiFetch<ClienteSugerido[]>(`/clientes/?${query.toString()}`, { signal })
}
