import type { ClienteSugerido } from '../types'
import { apiFetch } from './client'

/**
 * HU-12: clientes registrados. Sin texto lista los primeros por orden alfabético (con
 * `limite` alto, alimenta el selector del formulario y el filtro del historial).
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

/** Solo la superadministradora registra, renombra y borra clientes. */
export async function crearCliente(nombre: string): Promise<ClienteSugerido> {
  return apiFetch<ClienteSugerido>('/clientes/', {
    method: 'POST',
    body: JSON.stringify({ nombre }),
  })
}

export async function renombrarCliente(id: string, nombre: string): Promise<ClienteSugerido> {
  return apiFetch<ClienteSugerido>(`/clientes/${id}`, {
    method: 'PATCH',
    body: JSON.stringify({ nombre }),
  })
}

export async function borrarCliente(id: string): Promise<void> {
  await apiFetch<boolean>(`/clientes/${id}`, { method: 'DELETE' })
}
