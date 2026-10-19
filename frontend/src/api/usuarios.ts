import type { Rol, Usuario } from '../types'
import { apiFetch } from './client'

/** HU-03: gestión de usuarios. */

export interface NuevoUsuario {
  nombre: string
  correo: string
  password: string
  rol: Exclude<Rol, 'SUPERADMINISTRADOR'>
}

export interface CambiosUsuario {
  nombre?: string
  correo?: string
  rol?: Exclude<Rol, 'SUPERADMINISTRADOR'>
  /** `true` aprueba una cuenta pendiente o reactiva; `false` inactiva. */
  activo?: boolean
}

export const listarUsuarios = () => apiFetch<Usuario[]>('/auth/usuarios')

export const crearUsuario = (datos: NuevoUsuario) =>
  apiFetch<Usuario>('/auth/usuarios', { method: 'POST', body: JSON.stringify(datos) })

export const actualizarUsuario = (id: string, cambios: CambiosUsuario) =>
  apiFetch<Usuario>(`/auth/usuarios/${id}`, { method: 'PATCH', body: JSON.stringify(cambios) })
