/**
 * Cliente HTTP centralizado. Inyecta el token en cada petición y traduce los
 * errores del backend a mensajes que la interfaz puede mostrar tal cual.
 */

const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'
const CLAVE_SESION = 'beematch_sesion'

export function guardarSesion(sesion: unknown): void {
  localStorage.setItem(CLAVE_SESION, JSON.stringify(sesion))
}

export function leerSesion<T>(): T | null {
  try {
    const guardada = localStorage.getItem(CLAVE_SESION)
    return guardada ? (JSON.parse(guardada) as T) : null
  } catch {
    return null
  }
}

export function borrarSesion(): void {
  localStorage.removeItem(CLAVE_SESION)
}

function obtenerToken(): string | null {
  const sesion = leerSesion<{ access_token?: string }>()
  return sesion?.access_token ?? null
}

function mensajeDeError(cuerpo: { detail?: unknown }, status: number): string {
  const { detail } = cuerpo
  if (Array.isArray(detail)) {
    return detail
      .map((e: { loc?: string[]; msg?: string }) => {
        const campo = e.loc?.[e.loc.length - 1] ?? 'campo'
        return `${campo}: ${e.msg}`
      })
      .join('. ')
  }
  if (typeof detail === 'string') return detail
  return `Error ${status}`
}

export async function apiFetch<T>(
  ruta: string,
  opciones: RequestInit = {},
  requiereAuth = true,
): Promise<T> {
  const headers: Record<string, string> = {
    ...((opciones.headers as Record<string, string>) || {}),
  }

  if (opciones.body && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json'
  }

  if (requiereAuth) {
    const token = obtenerToken()
    if (token) headers['Authorization'] = `Bearer ${token}`
  }

  const respuesta = await fetch(`${BASE_URL}${ruta}`, { ...opciones, headers })

  if (respuesta.status === 401) {
    borrarSesion()
    const cuerpo = await respuesta.json().catch(() => ({}))
    throw new Error(cuerpo.detail || 'La sesión expiró. Inicia sesión nuevamente.')
  }

  if (!respuesta.ok) {
    const cuerpo = await respuesta.json().catch(() => ({}))
    throw new Error(mensajeDeError(cuerpo, respuesta.status))
  }

  if (respuesta.status === 204) return true as T
  return respuesta.json() as Promise<T>
}

export { BASE_URL }