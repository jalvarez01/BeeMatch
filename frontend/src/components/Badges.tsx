import type { EstadoSolicitud, NivelAfinidad } from '../types'

const ETIQUETA_ESTADO: Record<EstadoSolicitud, string> = {
  PROCESADA: 'Procesada',
  EN_ANALISIS: 'En análisis',
  BORRADOR: 'Borrador',
  ERROR: 'Sin coincidencias',
}

const CLASE_ESTADO: Record<EstadoSolicitud, string> = {
  PROCESADA: 'bm-badge-green',
  EN_ANALISIS: 'bm-badge-yellow',
  BORRADOR: 'bm-badge-gray',
  ERROR: 'bm-badge-red',
}

export function EstadoBadge({ estado }: { estado: EstadoSolicitud }) {
  return <span className={`bm-badge ${CLASE_ESTADO[estado]}`}>{ETIQUETA_ESTADO[estado]}</span>
}

const ETIQUETA_NIVEL: Record<NivelAfinidad, string> = {
  ALTA: 'Afinidad alta',
  MEDIA: 'Afinidad media',
  BAJA: 'Afinidad baja',
}

export function AfinidadBadge({ nivel }: { nivel: NivelAfinidad }) {
  const clase = nivel === 'ALTA' ? 'bm-badge-green' : nivel === 'MEDIA' ? 'bm-badge-yellow' : 'bm-badge-gray'
  return <span className={`bm-badge ${clase}`}>{ETIQUETA_NIVEL[nivel]}</span>
}

export function Tag({ children }: { children: React.ReactNode }) {
  return <span className="bm-tag">{children}</span>
}
