import type { EstadoSolicitud, NivelAfinidad } from '../types'

const ETIQUETA_ESTADO: Record<EstadoSolicitud, string> = {
  PROCESADA: 'Procesada',
  EN_ANALISIS: 'En análisis',
  BORRADOR: 'Borrador',
  SIN_COINCIDENCIAS: 'Sin coincidencias',
  ERROR: 'Error',
}

const CLASE_ESTADO: Record<EstadoSolicitud, string> = {
  PROCESADA: 'bm-badge-green',
  EN_ANALISIS: 'bm-badge-yellow',
  BORRADOR: 'bm-badge-gray',
  SIN_COINCIDENCIAS: 'bm-badge-red',
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

// HU-20: "baja" va en naranja para no confundirse con el gris de Borrador.
const CLASE_NIVEL: Record<NivelAfinidad, string> = {
  ALTA: 'bm-badge-green',
  MEDIA: 'bm-badge-yellow',
  BAJA: 'bm-badge-orange',
}

const CLASE_TEXTO_NIVEL: Record<NivelAfinidad, string> = {
  ALTA: 'bm-nivel-alta',
  MEDIA: 'bm-nivel-media',
  BAJA: 'bm-nivel-baja',
}

// Cortes de nivel_de en backend/domain/matching/scorer.py.
const RANGO_NIVEL: Record<NivelAfinidad, string> = {
  ALTA: '85% o más',
  MEDIA: 'de 70% a menos de 85%',
  BAJA: 'menos de 70%',
}

export function AfinidadBadge({ nivel }: { nivel: NivelAfinidad }) {
  return <span className={`bm-badge ${CLASE_NIVEL[nivel]}`}>{ETIQUETA_NIVEL[nivel]}</span>
}

/** Porcentaje de afinidad con el color de su nivel. */
export function AfinidadPorcentaje({
  puntaje,
  nivel,
  className = '',
  style,
}: {
  puntaje: number
  nivel: NivelAfinidad
  className?: string
  style?: React.CSSProperties
}) {
  return (
    <div className={`${className} ${CLASE_TEXTO_NIVEL[nivel]}`.trim()} style={style}>
      {puntaje}%
    </div>
  )
}

export function LeyendaAfinidad() {
  return (
    <div className="bm-leyenda" aria-label="Niveles de afinidad">
      {(['ALTA', 'MEDIA', 'BAJA'] as const).map((nivel) => (
        <span key={nivel}>
          <AfinidadBadge nivel={nivel} /> {RANGO_NIVEL[nivel]}
        </span>
      ))}
    </div>
  )
}

export function Tag({ children }: { children: React.ReactNode }) {
  return <span className="bm-tag">{children}</span>
}
