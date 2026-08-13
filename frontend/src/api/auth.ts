import type { Sesion, Usuario } from '../types'
import { apiFetch, borrarSesion, guardarSesion } from './client'

export async function iniciarSesion(correo: string, password: string): Promise<Sesion> {
  const sesion = await apiFetch<Sesion>(
    '/auth/login',
    { method: 'POST', body: JSON.stringify({ correo, password }) },
    false,
  )
  guardarSesion(sesion)
  return sesion
}

export function cerrarSesion(): void {
  borrarSesion()
}

export async function usuarioActual(): Promise<Usuario> {
  return apiFetch<Usuario>('/auth/yo')
}
