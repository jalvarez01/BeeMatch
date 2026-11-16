import type { Rol, Usuario } from '../types'
import { apiFetch } from './client'

/** HU-03 y HU-04: gestión de usuarios. */

export interface CrearUsuarioPayload {
  nombre: string
  correo: string
  password: string
  rol: Exclude<Rol, 'SUPERADMINISTRADOR'>
}

export interface CambiosUsuario {
  nombre?: string
  correo?: string
  rol?: Exclude<Rol, 'SUPERADMINISTRADOR'>
  /** `true` reactiva la cuenta; `false` la inactiva. */
  activo?: boolean
}

export async function listarUsuarios(): Promise<Usuario[]> {
  return apiFetch<Usuario[]>('/auth/usuarios')
}

export async function crearUsuario(
  datos: CrearUsuarioPayload,
): Promise<Usuario> {
  return apiFetch<Usuario>('/auth/usuarios', {
    method: 'POST',
    body: JSON.stringify(datos),
  })
}

export async function actualizarUsuario(
  id: string,
  cambios: CambiosUsuario,
): Promise<Usuario> {
  return apiFetch<Usuario>(`/auth/usuarios/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(cambios),
  })
}
/** Borra el perfil. El historial de solicitudes de esa persona se conserva. */
export async function eliminarUsuario(id: string): Promise<void> {
  await apiFetch<boolean>(`/auth/usuarios/${id}`, { method: 'DELETE' })
}
