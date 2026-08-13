import { apiFetch } from './client'

export interface CandidatoDetalle {
  id: string
  nombre: string
  rol_principal: string | null
  anios_experiencia: number | null
  ubicacion: string | null
  idiomas: string | null
  resumen: string | null
  hoja_de_vida_id: string
  nombre_archivo: string | null
  ruta_hoja_vida: string | null
  url_hoja_vida: string | null
  habilidades: { nombre: string; categoria: string; anios_experiencia: number | null }[]
}

export async function obtenerCandidato(id: string): Promise<CandidatoDetalle> {
  return apiFetch<CandidatoDetalle>(`/candidatos/${id}`)
}

export async function listarCandidatos(pagina = 1): Promise<CandidatoDetalle[]> {
  return apiFetch<CandidatoDetalle[]>(`/candidatos/?pagina=${pagina}`)
}
