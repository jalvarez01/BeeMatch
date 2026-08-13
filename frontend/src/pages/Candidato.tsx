import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { marcarPreseleccion, obtenerRecomendacion } from '../api/busquedas'
import { AfinidadBadge, Tag } from '../components/Badges'
import { IconSpark, IconUser } from '../components/Icons'
import type { Recomendacion } from '../types'

/** HU-19, HU-21, HU-24: explicación con evidencia y ubicación del CV. */
export default function Candidato() {
  const { recomendacionId = '' } = useParams()
  const navegar = useNavigate()

  const [candidato, setCandidato] = useState<Recomendacion | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    obtenerRecomendacion(recomendacionId)
      .then(setCandidato)
      .catch((e: Error) => setError(e.message))
  }, [recomendacionId])

  const alternar = async () => {
    if (!candidato) return
    const actualizado = await marcarPreseleccion(candidato.id, !candidato.preseleccionado)
    setCandidato({ ...candidato, preseleccionado: actualizado.preseleccionado })
  }

  if (error) return <div className="bm-alert bm-alert-error">{error}</div>
  if (!candidato) return <p style={{ color: 'var(--muted)' }}>Cargando el perfil…</p>

  const encontrados = candidato.coincidencias.filter((c) => c.estado !== 'NO_EVIDENCIADO')
  const enRevision = candidato.coincidencias.filter((c) => c.estado === 'NO_EVIDENCIADO')

  return (
    <>
      <button className="bm-btn-back" style={{ fontSize: 15 }} onClick={() => navegar(-1)}>
        ← Volver a resultados
      </button>

      <div className="bm-card">
        <div className="bm-row-between" style={{ flexWrap: 'wrap', gap: 16 }}>
          <div style={{ display: 'flex', gap: 16, alignItems: 'flex-start' }}>
            <div className="bm-avatar" style={{ width: 46, height: 46 }}>
              <IconUser />
            </div>
            <div>
              <h1 className="bm-h1" style={{ fontSize: 19, marginBottom: 2 }}>
                {candidato.nombre}
              </h1>
              <p style={{ fontSize: 12, color: 'var(--muted)', margin: '0 0 8px' }}>
                {candidato.rol_principal} · {candidato.anios_experiencia} años de experiencia
              </p>
              <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                {candidato.tecnologias.map((t) => (
                  <Tag key={t}>{t}</Tag>
                ))}
              </div>
            </div>
          </div>

          <div style={{ textAlign: 'right' }}>
            <div style={{ fontSize: 22, fontWeight: 700 }}>{candidato.puntaje_afinidad}%</div>
            <AfinidadBadge nivel={candidato.nivel} />
          </div>
        </div>

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 16 }}>
          <label
            className="bm-check"
            style={{
              background: 'var(--yellow-soft)',
              border: '1px solid var(--yellow-line)',
              borderRadius: 8,
              padding: '7px 12px',
            }}
          >
            <input type="checkbox" checked={candidato.preseleccionado} onChange={() => void alternar()} />
            {candidato.preseleccionado ? 'Preseleccionado' : 'Preseleccionar'}
          </label>

          {/* HU-21: enlace directo al documento en OneDrive. */}
          <a
            className="bm-btn bm-btn-dark"
            href={candidato.url_hoja_vida ?? '#'}
            target="_blank"
            rel="noreferrer"
            title={candidato.ruta_hoja_vida ?? ''}
          >
            Ver hoja de vida ↗
          </a>
        </div>
      </div>

      <div className="bm-cols" style={{ marginTop: 16 }}>
        <div className="bm-card" style={{ marginTop: 0 }}>
          <div className="bm-h3" style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <IconSpark /> Análisis de BeeMatch
          </div>
          <p style={{ fontSize: 12, color: 'var(--muted)', margin: '0 0 16px' }}>
            ¿Por qué este perfil tiene {candidato.puntaje_afinidad}% de afinidad?
          </p>

          <div className="bm-req">
            <div>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>
                Requisitos encontrados
              </div>
              {encontrados.map((c) => (
                <div className="bm-req-item" key={c.requisito}>
                  <span className="ok">✓ {c.requisito}</span>
                  <span className="ev">{c.evidencia_texto}</span>
                </div>
              ))}
              {encontrados.length === 0 && (
                <p style={{ fontSize: 12, color: 'var(--muted)' }}>
                  No se identificaron requisitos con evidencia en el documento.
                </p>
              )}
            </div>

            <div>
              <div style={{ fontSize: 12, fontWeight: 600, marginBottom: 8 }}>Requiere revisión</div>
              {enRevision.map((c) => (
                <div className="bm-warn" key={c.requisito} style={{ marginBottom: 8 }}>
                  <div className="r">! {c.requisito}</div>
                  {/* RNF27: ausencia de evidencia, no ausencia de la habilidad. */}
                  <div className="m">No se encontró evidencia explícita en la hoja de vida.</div>
                </div>
              ))}
              {enRevision.length === 0 && (
                <p style={{ fontSize: 12, color: 'var(--muted)' }}>
                  Todos los requisitos solicitados tienen evidencia en el documento.
                </p>
              )}
            </div>
          </div>
        </div>

        <div className="bm-card" style={{ marginTop: 0 }}>
          <h3 className="bm-h2" style={{ fontSize: 14 }}>
            Información del perfil
          </h3>
          <Campo etiqueta="Rol actual" valor={candidato.rol_principal} />
          <Campo
            etiqueta="Experiencia"
            valor={candidato.anios_experiencia ? `${candidato.anios_experiencia} años` : null}
          />
          <Campo etiqueta="Ubicación" valor={candidato.ubicacion} />
          <Campo etiqueta="Hoja de vida" valor={candidato.ruta_hoja_vida} />
        </div>
      </div>
    </>
  )
}

function Campo({ etiqueta, valor }: { etiqueta: string; valor: string | null }) {
  return (
    <div style={{ marginTop: 14 }}>
      <div className="bm-label">{etiqueta}</div>
      <div style={{ fontSize: 13 }}>{valor ?? 'No especificado'}</div>
    </div>
  )
}
