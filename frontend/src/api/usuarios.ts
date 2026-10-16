import type { Rol, Usuario } from '../types'
import { apiFetch } from './client'

export interface CrearUsuarioPayload {
  nombre: string
  correo: string
  password: string
  rol: Rol
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
  datos: { rol?: Rol; activo?: boolean },
): Promise<Usuario> {
  return apiFetch<Usuario>(`/auth/usuarios/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(datos),
  })
}
