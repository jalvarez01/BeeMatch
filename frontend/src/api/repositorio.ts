import { apiFetch } from './client'

/** Orígenes de hojas de vida soportados por el backend (HU-05). */
export type TipoRepositorio = 'ONEDRIVE' | 'GDRIVE'

/**
 * Credenciales del origen. La forma depende del `tipo`:
 *
 * - ONEDRIVE: tenant_id, client_id, client_secret, drive_id
 * - GDRIVE:   credenciales_json (el archivo de la cuenta de servicio)
 *
 * Los campos secretos pueden omitirse: el backend reutiliza el valor
 * almacenado del mismo proveedor.
 */
export type Credenciales = Record<string, string>

export interface ConexionRepositorio {
  configurado: boolean
  tipo: TipoRepositorio | null
  carpeta: string | null
  /** El backend nunca devuelve los secretos en claro, solo enmascarados. */
  credenciales: Credenciales
  secreto_legible: boolean
  ultima_validacion: string | null
  documentos_detectados: number | null
}

export interface ConexionPayload {
  tipo: TipoRepositorio
  carpeta: string
  credenciales: Credenciales
}

export interface PruebaConexion {
  exito: boolean
  documentos_detectados: number
  mensaje: string
  detalle: string | null
}

export interface GuardarConexion {
  guardado: boolean
  prueba: PruebaConexion
  configuracion: ConexionRepositorio | null
}

export async function obtenerConexion(): Promise<ConexionRepositorio> {
  return apiFetch<ConexionRepositorio>('/configuracion/repositorio')
}

/** Valida sin guardar. */
export async function probarConexion(datos: ConexionPayload): Promise<PruebaConexion> {
  return apiFetch<PruebaConexion>('/configuracion/repositorio/probar', {
    method: 'POST',
    body: JSON.stringify(datos),
  })
}

/** Revalida la conexión ya guardada y actualiza el conteo de documentos. */
export async function probarConexionGuardada(): Promise<PruebaConexion> {
  return apiFetch<PruebaConexion>('/configuracion/repositorio/probar-guardada', { method: 'POST' })
}

/** Guarda solo si la conexión es válida; si no, la anterior queda intacta. */
export async function guardarConexion(datos: ConexionPayload): Promise<GuardarConexion> {
  return apiFetch<GuardarConexion>('/configuracion/repositorio', {
    method: 'PUT',
    body: JSON.stringify(datos),
  })
}
