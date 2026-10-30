import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { eliminarSolicitud, listarHistorial } from '../api/solicitudes'
import { EstadoBadge } from '../components/Badges'
import EstadoVacio from '../components/EstadoVacio'
import type { Solicitud } from '../types'

/** Solicitudes en curso: borradores y análisis en ejecución. */
export default function Solicitudes() {
  const navegar = useNavigate()
  const [solicitudes, setSolicitudes] = useState<Solicitud[]>([])
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([
      listarHistorial({ estado: 'BORRADOR' }),
      listarHistorial({ estado: 'EN_ANALISIS' }),
    ])
      .then(([borradores, enAnalisis]) =>
        setSolicitudes([...enAnalisis.solicitudes, ...borradores.solicitudes]),
      )
      .catch(() => setSolicitudes([]))
  }, [])

  const eliminar = async (solicitud: Solicitud) => {
    if (!window.confirm('¿Eliminar este borrador? Esta acción no se puede deshacer.')) return
    setError('')
    try {
      await eliminarSolicitud(solicitud.id)
      setSolicitudes((actuales) => actuales.filter((item) => item.id !== solicitud.id))
    } catch (e) {
      setError((e as Error).message)
    }
  }

  if (solicitudes.length === 0) {
    return (
      <>
        <h1 className="bm-h1">Solicitudes activas</h1>
        <p className="bm-sub">Borradores y análisis en curso.</p>
        {error && <div className="bm-alert bm-alert-error">{error}</div>}
        <EstadoVacio
          titulo="No hay solicitudes activas"
          texto="Cuando guardes un borrador o ejecutes una búsqueda, aparecerá aquí."
          accion={
            <button
              className="bm-btn bm-btn-primary"
              style={{ marginTop: 14 }}
              onClick={() => navegar('/nueva-busqueda')}
            >
              Nueva búsqueda
            </button>
          }
        />
      </>
    )
  }

  return (
    <>
      <h1 className="bm-h1">Solicitudes activas</h1>
      <p className="bm-sub">Borradores y análisis en curso.</p>
      {error && <div className="bm-alert bm-alert-error">{error}</div>}

      <div className="bm-card">
        {solicitudes.map((solicitud) => (
          <div className="bm-hist-row" key={solicitud.id}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>
                {solicitud.rol_buscado ?? 'Sin rol definido'}
              </div>
              {solicitud.descripcion_libre?.trim() && (
                <div className="bm-solicitud-desc">{solicitud.descripcion_libre}</div>
              )}
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                {solicitud.cliente_nombre} · {solicitud.proyecto_nombre}
              </div>
            </div>
            <div />
            <EstadoBadge estado={solicitud.estado} />
            <button
              className="bm-btn bm-btn-ghost"
              onClick={() => navegar(`/nueva-busqueda?solicitud=${solicitud.id}`)}
            >
              Abrir →
            </button>
            {solicitud.estado === 'BORRADOR' && (
              <button
                className="bm-btn bm-btn-compact bm-btn-delete"
                onClick={() => void eliminar(solicitud)}
              >
                Eliminar
              </button>
            )}
          </div>
        ))}
      </div>
    </>
  )
}
