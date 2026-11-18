import type { Sesion, Usuario } from '../types'
import { apiFetch, borrarSesion, guardarSesion, leerSesion } from './client'

export async function iniciarSesion(correo: string, password: string): Promise<Sesion> {
  const sesion = await apiFetch<Sesion>(
    '/auth/login',
    { method: 'POST', body: JSON.stringify({ correo, password }) },
    false,
  )
  guardarSesion(sesion)
  return sesion
}

/** HU-02: avisa al servidor para la bitácora y descarta la sesión local pase lo que pase. */
export async function cerrarSesion(): Promise<void> {
  try {
    await apiFetch<boolean>('/auth/logout', { method: 'POST' })
  } catch {
    // Sin conexión o con la sesión ya vencida: igual se cierra en el navegador.
  } finally {
    borrarSesion()
  }
}

/** HU-02: pide un token nuevo mientras el usuario sigue activo. */
export async function renovarSesion(): Promise<void> {
  const sesion = await apiFetch<Sesion>('/auth/renovar', { method: 'POST' })
  guardarSesion(sesion)
}

export interface DatosCambioPassword {
  password_actual: string
  password_nueva: string
}

/** Cambio de contraseña propio. Quita la marca de "debe cambiarla" de la sesión guardada. */
export async function cambiarPassword(datos: DatosCambioPassword): Promise<Usuario> {
  const usuario = await apiFetch<Usuario>('/auth/cambiar-password', {
    method: 'POST',
    body: JSON.stringify(datos),
  })
  const sesion = leerSesion<Sesion>()
  if (sesion) guardarSesion({ ...sesion, usuario: { ...sesion.usuario, ...usuario } })
  return usuario
}

export async function usuarioActual(): Promise<Usuario> {
  return apiFetch<Usuario>('/auth/yo')
}
