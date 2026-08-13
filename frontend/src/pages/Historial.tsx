import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { ejecutarBusqueda } from '../api/busquedas'
import { duplicarSolicitud, listarHistorial } from '../api/solicitudes'
import { EstadoBadge } from '../components/Badges'
import { IconSearch } from '../components/Icons'
import type { EstadoSolicitud, Solicitud } from '../types'

const FILTROS: { valor: EstadoSolicitud | ''; etiqueta: string }[] = [
  { valor: '', etiqueta: 'Todos' },
  { valor: 'PROCESADA', etiqueta: 'Procesada' },
  { valor: 'EN_ANALISIS', etiqueta: 'En análisis' },
  { valor: 'BORRADOR', etiqueta: 'Borrador' },
]

const POR_PAGINA = 10

/** HU-13, HU-14, HU-15. */
export default function Historial() {
  const navegar = useNavigate()

  const [solicitudes, setSolicitudes] = useState<Solicitud[]>([])
  const [total, setTotal] = useState(0)
  const [filtro, setFiltro] = useState<EstadoSolicitud | ''>('')
  const [texto, setTexto] = useState('')
  const [pagina, setPagina] = useState(1)
  const [error, setError] = useState('')

  const cargar = useCallback(async () => {
    setError('')
    try {
      const respuesta = await listarHistorial({
        estado: filtro || undefined,
        texto: texto || undefined,
        pagina,
      })
      setSolicitudes(respuesta.solicitudes)
      setTotal(respuesta.total)
    } catch (e) {
      setError((e as Error).message)
    }
  }, [filtro, texto, pagina])

  useEffect(() => {
    void cargar()
  }, [cargar])

  const duplicar = async (solicitudId: string) => {
    const copia = await duplicarSolicitud(solicitudId)
    navegar(`/nueva-busqueda?solicitud=${copia.id}`)
  }

  const reejecutar = async (solicitudId: string) => {
    const busqueda = await ejecutarBusqueda(solicitudId)
    navegar(`/resultados/${busqueda.id}`)
  }

  const paginas = Math.max(1, Math.ceil(total / POR_PAGINA))

  return (
    <>
      <h1 className="bm-h1">Historial de solicitudes</h1>
      <p className="bm-sub">Consulta, filtra y reutiliza las solicitudes de staffing realizadas.</p>

      {error && <div className="bm-alert bm-alert-error">{error}</div>}

      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <div className="bm-search">
          <IconSearch />
          <input
            placeholder="Buscar por rol, cliente o proyecto…"
            value={texto}
            onChange={(e) => {
              setTexto(e.target.value)
              setPagina(1)
            }}
            aria-label="Buscar solicitudes"
          />
        </div>
        <button className="bm-btn bm-btn-primary" onClick={() => navegar('/nueva-busqueda')}>
          + Nueva búsqueda
        </button>
      </div>

      <div className="bm-filters">
        {FILTROS.map((f) => (
          <button
            key={f.etiqueta}
            data-active={filtro === f.valor}
            onClick={() => {
              setFiltro(f.valor)
              setPagina(1)
            }}
          >
            {f.etiqueta}
          </button>
        ))}
      </div>

      <div className="bm-card">
        <div className="bm-row-between" style={{ marginBottom: 6 }}>
          <h2 className="bm-h2" style={{ margin: 0 }}>
            Solicitudes
          </h2>
          <span style={{ fontSize: 12, color: 'var(--muted-2)' }}>{total} solicitudes</span>
        </div>

        {solicitudes.length === 0 && (
          <div className="bm-empty">
            <h3>No hay solicitudes con esos criterios</h3>
            <p>Cambia el filtro o crea una nueva búsqueda.</p>
          </div>
        )}

        {solicitudes.map((solicitud) => (
          <div className="bm-hist-row" key={solicitud.id}>
            <div>
              <div style={{ fontSize: 13, fontWeight: 600 }}>
                {solicitud.rol_buscado ?? 'Sin rol definido'}
              </div>
              <div style={{ fontSize: 12, color: 'var(--muted)' }}>
                {solicitud.cliente_nombre} · {solicitud.proyecto_nombre}
              </div>
              <div style={{ fontSize: 11, color: 'var(--muted-2)', marginTop: 6 }}>
                {formatearFecha(solicitud.created_at)} · Creada por {solicitud.usuario_nombre}
              </div>
            </div>

            <div style={{ fontSize: 12 }}>
              {solicitud.total_candidatos != null && <div>{solicitud.total_candidatos} candidatos</div>}
              {solicitud.mejor_afinidad != null && (
                <div style={{ color: 'var(--muted)' }}>{solicitud.mejor_afinidad}% mejor afinidad</div>
              )}
              {solicitud.estado === 'EN_ANALISIS' && (
                <div style={{ color: 'var(--muted)' }}>Analizando perfiles…</div>
              )}
            </div>

            <EstadoBadge estado={solicitud.estado} />

            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-end' }}>
              {solicitud.estado === 'PROCESADA' && (
                <>
                  <button className="bm-btn bm-btn-ghost" onClick={() => void duplicar(solicitud.id)}>
                    Duplicar
                  </button>
                  <button
                    className="bm-btn bm-btn-dark"
                    onClick={() => navegar(`/resultados/${solicitud.busqueda_id}`)}
                  >
                    Ver resultados →
                  </button>
                </>
              )}

              {solicitud.estado === 'EN_ANALISIS' && (
                <button
                  className="bm-btn bm-btn-ghost"
                  onClick={() => navegar(`/resultados/${solicitud.busqueda_id}`)}
                >
                  Ver solicitud →
                </button>
              )}

              {solicitud.estado === 'BORRADOR' && (
                <button
                  className="bm-btn bm-btn-ghost"
                  onClick={() => navegar(`/nueva-busqueda?solicitud=${solicitud.id}`)}
                >
                  Continuar editando →
                </button>
              )}

              {solicitud.estado === 'ERROR' && (
                <button className="bm-btn bm-btn-ghost" onClick={() => void reejecutar(solicitud.id)}>
                  Reintentar →
                </button>
              )}
            </div>
          </div>
        ))}

        <div className="bm-pager">
          <button onClick={() => setPagina((p) => Math.max(1, p - 1))} aria-label="Anterior">
            ←
          </button>
          {Array.from({ length: paginas }, (_, i) => i + 1).map((n) => (
            <button key={n} data-active={pagina === n} onClick={() => setPagina(n)}>
              {n}
            </button>
          ))}
          <button onClick={() => setPagina((p) => Math.min(paginas, p + 1))} aria-label="Siguiente">
            →
          </button>
        </div>
      </div>
    </>
  )
}

function formatearFecha(iso: string | null): string {
  if (!iso) return ''
  return new Date(iso).toLocaleDateString('es-CO', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
}
