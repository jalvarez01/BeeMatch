import { apiFetch } from './client'

/** HU-07: parámetros de recomendación que ajusta el administrador. */

export interface ParametrosRecomendacion {
  num_candidatos: number
  umbral_afinidad: number
  num_candidatos_por_defecto: number
  umbral_afinidad_por_defecto: number
  minimo_candidatos: number
  maximo_candidatos: number
  minimo_umbral: number
  maximo_umbral: number
}

export interface CambioParametros {
  num_candidatos: number
  umbral_afinidad: number
}

export async function obtenerParametros(): Promise<ParametrosRecomendacion> {
  return apiFetch<ParametrosRecomendacion>('/configuracion/recomendacion')
}

export async function guardarParametros(
  cambio: CambioParametros,
): Promise<ParametrosRecomendacion> {
  return apiFetch<ParametrosRecomendacion>('/configuracion/recomendacion', {
    method: 'PUT',
    body: JSON.stringify(cambio),
  })
}
