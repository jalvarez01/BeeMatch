import { useEffect, useState } from 'react'

import { listarCandidatos, type CandidatoDetalle } from '../api/candidatos'
import { Tag } from '../components/Badges'
import EstadoVacio from '../components/EstadoVacio'

/** Repositorio de candidatos indexados desde OneDrive. */
export default function Candidatos() {
  const [candidatos, setCandidatos] = useState<CandidatoDetalle[]>([])
  const [cargando, setCargando] = useState(true)

  useEffect(() => {
    listarCandidatos()
      .then(setCandidatos)
      .catch(() => setCandidatos([]))
      .finally(() => setCargando(false))
  }, [])

  if (!cargando && candidatos.length === 0) {
    return (
      <>
        <h1 className="bm-h1">Candidatos</h1>
        <p className="bm-sub">Hojas de vida indexadas desde el repositorio de OneDrive.</p>
        <EstadoVacio
          titulo="Todavía no hay hojas de vida indexadas"
          texto="Ejecuta una sincronización desde Configuración para traer los documentos de OneDrive."
        />
      </>
    )
  }

  return (
    <>
      <h1 className="bm-h1">Candidatos</h1>
      <p className="bm-sub">Hojas de vida indexadas desde el repositorio de OneDrive.</p>

      <div className="bm-card">
        {candidatos.map((candidato) => (
          <div className="bm-hist-row" key={candidato.id}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>{candidato.nombre}</div>
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                {candidato.rol_principal ?? 'Rol no especificado'}
                {candidato.anios_experiencia ? ` · ${candidato.anios_experiencia} años` : ''}
              </div>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', marginTop: 8 }}>
                {candidato.habilidades.slice(0, 6).map((h) => (
                  <Tag key={h.nombre}>{h.nombre}</Tag>
                ))}
              </div>
            </div>
            <div style={{ fontSize: 11, color: 'var(--muted-2)' }}>{candidato.ruta_hoja_vida}</div>
            <div />
            <a
              className="bm-btn bm-btn-ghost"
              href={candidato.url_hoja_vida ?? '#'}
              target="_blank"
              rel="noreferrer"
            >
              Ver CV ↗
            </a>
          </div>
        ))}
      </div>
    </>
  )
}
