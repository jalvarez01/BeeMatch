/** Fecha corta, para el historial de solicitudes. */
export function formatearFecha(iso: string | null): string {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('es-CO', { day: '2-digit', month: 'short', year: 'numeric' })
}

/** Fecha y hora, para distinguir una ejecución de otra (HU-15). */
export function formatearFechaHora(iso: string | null): string {
  if (!iso) return ''
  return new Date(iso).toLocaleString('es-CO', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

interface ResumibleParametros {
  cliente: string | null
  proyecto: string | null
  experiencia_min: number | null
  criterios: { valor: string }[]
}

/** Una línea con lo que se pidió en una ejecución: cliente, proyecto, criterios y experiencia. */
export function resumirParametros(parametros: ResumibleParametros | null): string {
  if (!parametros) return 'Criterios no registrados (ejecución anterior a esta función)'
  return [
    [parametros.cliente, parametros.proyecto].filter(Boolean).join(' · '),
    parametros.criterios.map((c) => c.valor).join(', '),
    parametros.experiencia_min ? `${parametros.experiencia_min}+ años` : '',
  ]
    .filter(Boolean)
    .join(' — ')
}

const ETIQUETA_ESTADO: Record<string, string> = {
  EN_COLA: 'En cola',
  EJECUTANDO: 'En análisis',
  COMPLETADA: 'Completada',
  ERROR: 'Con error',
}

export function etiquetaDeEstadoBusqueda(estado: string): string {
  return ETIQUETA_ESTADO[estado] ?? estado
}
