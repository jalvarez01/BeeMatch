import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { obtenerDashboard } from '../api/dashboard'
import { leerSesion } from '../api/client'
import { IconSpark } from '../components/Icons'
import type { Dashboard as DashboardData, EstadoSolicitud, Sesion } from '../types'

const CLASE_RECIENTE: Record<EstadoSolicitud, string> = {
  PROCESADA: 'ok',
  EN_ANALISIS: 'wip',
  BORRADOR: 'wip',
  ERROR: 'err',
}

const ETIQUETA_RECIENTE: Record<EstadoSolicitud, string> = {
  PROCESADA: 'Procesada',
  EN_ANALISIS: 'En análisis',
  BORRADOR: 'Borrador',
  ERROR: 'Sin coincidencias',
}

export default function Dashboard() {
  const navegar = useNavigate()
  const usuario = leerSesion<Sesion>()?.usuario
  const [datos, setDatos] = useState<DashboardData | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    obtenerDashboard()
      .then(setDatos)
      .catch((e: Error) => setError(e.message))
  }, [])

  return (
    <>
      <div className="bm-row-between" style={{ marginBottom: 22 }}>
        <div>
          <h1 className="bm-h1">Buen día, {usuario?.nombre ?? ''}</h1>
          <p style={{ color: 'var(--muted)', margin: 0 }}>
            Aquí tienes un resumen de la actividad de staffing.
          </p>
        </div>
        <button className="bm-btn bm-btn-primary" onClick={() => navegar('/nueva-busqueda')}>
          Nueva búsqueda con IA
        </button>
      </div>

      {error && <div className="bm-alert bm-alert-error">{error}</div>}

      <div className="bm-dark">
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontWeight: 600 }}>
          Resumen inteligente <IconSpark />
        </div>
        <p style={{ color: '#A1A1A6', fontSize: 12, margin: '6px 0 0' }}>
          BeeMatch analizó la actividad reciente y encontró nuevas oportunidades para tus solicitudes.
        </p>
        <div className="bm-metrics">
          <div>
            <div className="n">{datos?.candidatos_alta_afinidad ?? '—'}</div>
            <div className="l">candidatos con alta afinidad</div>
          </div>
          <div>
            <div className="n">{datos?.perfiles_nuevos ?? '—'}</div>
            <div className="l">perfiles nuevos</div>
          </div>
          <div>
            <div className="n">{datos?.solicitudes_sin_coincidencias ?? '—'}</div>
            <div className="l">solicitudes sin coincidencias</div>
          </div>
        </div>
      </div>

      <div className="bm-kpis">
        <div className="bm-kpi">
          <div className="l">Solicitudes activas</div>
          <div className="n">{datos?.solicitudes_activas ?? '—'}</div>
        </div>
        <div className="bm-kpi">
          <div className="l">Perfiles recomendados</div>
          <div className="n">{datos?.perfiles_recomendados ?? '—'}</div>
        </div>
        <div className="bm-kpi">
          <div className="l">Hojas de vida analizadas</div>
          <div className="n">{datos?.hojas_vida_analizadas ?? '—'}</div>
        </div>
        <div className="bm-kpi">
          <div className="l">Afinidad promedio</div>
          <div className="n">{datos ? `${datos.afinidad_promedio}%` : '—'}</div>
        </div>
      </div>

      <div className="bm-row-between" style={{ marginBottom: 12 }}>
        <h2 className="bm-h2" style={{ margin: 0 }}>
          Solicitudes recientes
        </h2>
        <button className="bm-btn-link" onClick={() => navegar('/historial')}>
          Ver historial
        </button>
      </div>

      <div className="bm-recent">
        {(datos?.recientes ?? []).map((solicitud) => (
          <button
            key={solicitud.id}
            className={CLASE_RECIENTE[solicitud.estado]}
            onClick={() => navegar(`/solicitudes/${solicitud.id}`)}
          >
            <span>
              {solicitud.cliente ? `${solicitud.cliente} · ` : ''}
              {solicitud.perfil} <b>({ETIQUETA_RECIENTE[solicitud.estado]})</b>
            </span>
            <span className="t">{solicitud.hace} →</span>
          </button>
        ))}

        {datos && datos.recientes.length === 0 && (
          <p style={{ color: 'var(--muted)', fontSize: 13 }}>
            Todavía no hay solicitudes. Crea la primera con el botón de arriba.
          </p>
        )}
      </div>
    </>
  )
}
