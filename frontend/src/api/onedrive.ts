import { apiFetch } from './client'

/** Configuración de conexión con OneDrive (HU-05). */
export interface ConexionOneDrive {
  configurado: boolean
  tenant_id: string | null
  client_id: string | null
  /** El backend nunca devuelve el secreto en claro, solo esta versión enmascarada. */
  client_secret_enmascarado: string | null
  secreto_legible: boolean
  drive_id: string | null
  carpeta_cv: string | null
  ultima_validacion: string | null
  documentos_detectados: number | null
}

export interface ConexionPayload {
  tenant_id: string
  client_id: string
  /** Opcional: si se omite, el backend reutiliza el secreto ya almacenado. */
  client_secret?: string
  drive_id: string
  carpeta_cv: string
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
  configuracion: ConexionOneDrive | null
}

export async function obtenerConexion(): Promise<ConexionOneDrive> {
  return apiFetch<ConexionOneDrive>('/configuracion/onedrive')
}

/** Valida sin guardar. */
export async function probarConexion(datos: ConexionPayload): Promise<PruebaConexion> {
  return apiFetch<PruebaConexion>('/configuracion/onedrive/probar', {
    method: 'POST',
    body: JSON.stringify(datos),
  })
}

/** Revalida la conexión ya guardada y actualiza el conteo de documentos. */
export async function probarConexionGuardada(): Promise<PruebaConexion> {
  return apiFetch<PruebaConexion>('/configuracion/onedrive/probar-guardada', { method: 'POST' })
}

/** Guarda solo si la conexión es válida; si no, la anterior queda intacta. */
export async function guardarConexion(datos: ConexionPayload): Promise<GuardarConexion> {
  return apiFetch<GuardarConexion>('/configuracion/onedrive', {
    method: 'PUT',
    body: JSON.stringify(datos),
  })
}
