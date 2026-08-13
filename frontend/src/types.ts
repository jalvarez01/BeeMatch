/** Tipos compartidos. Espejan los schemas de Pydantic del backend. */

export type Rol = 'COORDINADOR' | 'DIRECTOR' | 'ADMINISTRADOR'

export type EstadoSolicitud = 'BORRADOR' | 'EN_ANALISIS' | 'PROCESADA' | 'ERROR'

export type EstadoBusqueda = 'EN_COLA' | 'EJECUTANDO' | 'COMPLETADA' | 'ERROR'

export type EstadoCoincidencia = 'ENCONTRADO' | 'PARCIAL' | 'NO_EVIDENCIADO'

export type NivelAfinidad = 'ALTA' | 'MEDIA' | 'BAJA'

export type TipoCriterio =
  | 'TECNOLOGIA'
  | 'FRAMEWORK'
  | 'DOMINIO'
  | 'CERTIFICACION'
  | 'IDIOMA'

export interface Usuario {
  id: string
  nombre: string
  correo: string
  rol: Rol
  activo: boolean
}

export interface Sesion {
  access_token: string
  token_type: string
  usuario: Usuario
}

export interface Criterio {
  id?: string
  tipo: TipoCriterio
  valor: string
  obligatorio: boolean
  peso: number
}

export interface Solicitud {
  id: string
  descripcion_libre: string
  rol_buscado: string | null
  experiencia_min: number | null
  estado: EstadoSolicitud
  created_at: string | null
  cliente_nombre: string | null
  proyecto_nombre: string | null
  usuario_nombre: string | null
  criterios: Criterio[]
  total_candidatos: number | null
  mejor_afinidad: number | null
  busqueda_id: string | null
}

export interface Historial {
  total: number
  pagina: number
  solicitudes: Solicitud[]
}

export interface SolicitudPayload {
  descripcion_libre: string
  rol_buscado?: string | null
  experiencia_min?: number | null
  cliente?: string | null
  proyecto?: string | null
  criterios: Criterio[]
}

/**
 * NO_EVIDENCIADO significa que la hoja de vida no lo menciona, nunca que el
 * candidato carezca de la habilidad.
 */
export interface Coincidencia {
  requisito: string
  estado: EstadoCoincidencia
  evidencia_texto: string | null
  fragmento_id: string | null
}

export interface Recomendacion {
  id: string
  candidato_id: string
  posicion: number
  puntaje_afinidad: number
  nivel: NivelAfinidad
  preseleccionado: boolean
  resumen_ia: string | null
  nombre: string | null
  rol_principal: string | null
  anios_experiencia: number | null
  tecnologias: string[]
  ubicacion: string | null
  ruta_hoja_vida: string | null
  url_hoja_vida: string | null
  coincidencias: Coincidencia[]
}

export interface BusquedaEstado {
  id: string
  solicitud_id: string
  estado: EstadoBusqueda
  etapa: string | null
  progreso: number
  mensaje_error: string | null
}

export interface BusquedaResultado {
  id: string
  solicitud_id: string
  estado: EstadoBusqueda
  cv_analizados: number
  cv_no_procesables: number
  duracion_ms: number | null
  modelo_ia: string | null
  created_at: string | null
  recomendaciones: Recomendacion[]
}

export interface SolicitudReciente {
  id: string
  perfil: string
  cliente: string | null
  estado: EstadoSolicitud
  hace: string
}

export interface Dashboard {
  solicitudes_activas: number
  perfiles_recomendados: number
  hojas_vida_analizadas: number
  afinidad_promedio: number
  candidatos_alta_afinidad: number
  perfiles_nuevos: number
  solicitudes_sin_coincidencias: number
  recientes: SolicitudReciente[]
}
