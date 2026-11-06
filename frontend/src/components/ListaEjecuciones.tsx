import { etiquetaDeEstadoBusqueda, formatearFechaHora, resumirParametros } from '../lib/formato'
import type { EjecucionResumen } from '../types'

interface Props {
  ejecuciones: EjecucionResumen[]
  /** La ejecución que se está viendo, si hay una. */
  actualId?: string
  onAbrir: (busquedaId: string) => void
}

/**
 * HU-15: ejecuciones de una solicitud, de la más reciente a la más antigua. Cada una
 * muestra su fecha y hora, lo que se pidió y lo que salió, para distinguirlas.
 */
export default function ListaEjecuciones({ ejecuciones, actualId, onAbrir }: Props) {
  if (ejecuciones.length < 2) return null

  return (
    <section className="bm-card" aria-label="Ejecuciones de esta solicitud" style={{ marginBottom: 18 }}>
      <h2 className="bm-h2" style={{ marginTop: 0 }}>
        Ejecuciones de esta solicitud
      </h2>
      {ejecuciones.map((e) => {
        const actual = e.id === actualId
        return (
          <div className="bm-exec" key={e.id} data-actual={actual}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600, display: 'flex', gap: 8, alignItems: 'center' }}>
                Ejecución {e.numero} · {formatearFechaHora(e.created_at)}
                <span className="bm-tag">{e.es_mas_reciente ? 'Más reciente' : 'Anterior'}</span>
                {actual && <span className="bm-tag">Estás viendo esta</span>}
              </div>
              <div className="bm-exec-meta">
                {etiquetaDeEstadoBusqueda(e.estado)}
                {e.estado === 'COMPLETADA' &&
                  ` · ${e.total_candidatos} candidatos` +
                    (e.mejor_afinidad != null ? ` · ${e.mejor_afinidad}% mejor afinidad` : '')}
              </div>
              <div className="bm-exec-meta">{resumirParametros(e.parametros)}</div>
            </div>
            {!actual && (
              <button className="bm-btn bm-btn-ghost" onClick={() => onAbrir(e.id)}>
                Ver →
              </button>
            )}
          </div>
        )
      })}
    </section>
  )
}
