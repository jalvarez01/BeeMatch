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

export interface DatosRegistro {
  nombre: string
  correo: string
  password: string
}

/** HU-03: autorregistro. La cuenta queda pendiente de aprobación. */
export async function registrarse(datos: DatosRegistro): Promise<Usuario> {
  return apiFetch<Usuario>(
    '/auth/registro',
    { method: 'POST', body: JSON.stringify(datos) },
    false,
  )
}

export async function usuarioActual(): Promise<Usuario> {
  return apiFetch<Usuario>('/auth/yo')
}
