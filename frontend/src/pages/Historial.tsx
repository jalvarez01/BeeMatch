import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { ejecutarBusqueda } from '../api/busquedas'
import { listarClientes } from '../api/clientes'
import { duplicarSolicitud, eliminarSolicitud, listarHistorial } from '../api/solicitudes'
import { EstadoBadge } from '../components/Badges'
import CriteriosSolicitud from '../components/CriteriosSolicitud'
import { IconSearch } from '../components/Icons'
import { formatearFecha } from '../lib/formato'
import type { ClienteSugerido, EstadoSolicitud, Solicitud } from '../types'

const FILTROS: { valor: EstadoSolicitud | ''; etiqueta: string }[] = [
  { valor: '', etiqueta: 'Todos' },
  { valor: 'PROCESADA', etiqueta: 'Procesada' },
  { valor: 'EN_ANALISIS', etiqueta: 'En análisis' },
  { valor: 'BORRADOR', etiqueta: 'Borrador' },
  { valor: 'SIN_COINCIDENCIAS', etiqueta: 'Sin coincidencias' },
]

const POR_PAGINA = 10

/** HU-09, HU-12, HU-13, HU-14, HU-15. */
export default function Historial() {
  const navegar = useNavigate()

  const [solicitudes, setSolicitudes] = useState<Solicitud[]>([])
  const [total, setTotal] = useState(0)
  const [filtro, setFiltro] = useState<EstadoSolicitud | ''>('')
  const [texto, setTexto] = useState('')
  // HU-12: filtro por cliente. Vacío es "todos los clientes".
  const [clienteId, setClienteId] = useState('')
  const [clientes, setClientes] = useState<ClienteSugerido[]>([])
  const [pagina, setPagina] = useState(1)
  const [error, setError] = useState('')
  // HU-22: id de la solicitud que se está reintentando; bloquea otro clic mientras tanto.
  const [reintentando, setReintentando] = useState<string | null>(null)

  const cargar = useCallback(async () => {
    setError('')
    try {
      const respuesta = await listarHistorial({
        estado: filtro || undefined,
        texto: texto || undefined,
        clienteId: clienteId || undefined,
        pagina,
      })
      setSolicitudes(respuesta.solicitudes)
      setTotal(respuesta.total)
    } catch (e) {
      setError((e as Error).message)
    }
  }, [filtro, texto, clienteId, pagina])

  useEffect(() => {
    void cargar()
  }, [cargar])

  // Los clientes del filtro son los ya registrados; si no cargan, el historial se ve igual.
  useEffect(() => {
    listarClientes('', 100)
      .then(setClientes)
      .catch(() => setClientes([]))
  }, [])

  const duplicar = async (solicitudId: string) => {
    const copia = await duplicarSolicitud(solicitudId)
    navegar(`/nueva-busqueda?solicitud=${copia.id}`)
  }

  const eliminarBorrador = async (solicitudId: string) => {
    if (!window.confirm('¿Eliminar este borrador? Esta acción no se puede deshacer.')) return
    setError('')
    try {
      await eliminarSolicitud(solicitudId)
      await cargar()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const reejecutar = async (solicitudId: string) => {
    if (reintentando) return
    setError('')
    setReintentando(solicitudId)
    try {
      const busqueda = await ejecutarBusqueda(solicitudId)
      navegar(`/resultados/${busqueda.id}`)
    } catch (e) {
      setError((e as Error).message)
      setReintentando(null)
    }
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

      <div className="bm-filters" style={{ alignItems: 'center' }}>
        <label htmlFor="filtro-cliente" style={{ fontSize: 12, color: 'var(--muted)' }}>
          Cliente
        </label>
        <select
          id="filtro-cliente"
          value={clienteId}
          onChange={(e) => {
            setClienteId(e.target.value)
            setPagina(1)
          }}
          style={{ fontSize: 12, padding: '5px 10px', borderRadius: 8, border: '1px solid var(--line)' }}
        >
          <option value="">Todos los clientes</option>
          {clientes.map((c) => (
            <option key={c.id} value={c.id}>
              {c.nombre}
            </option>
          ))}
        </select>
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
                {[solicitud.cliente_nombre ?? 'Sin cliente', solicitud.proyecto_nombre]
                  .filter(Boolean)
                  .join(' · ')}
              </div>
              {/* HU-09: los criterios registrados quedan a la vista al consultar la solicitud. */}
              <CriteriosSolicitud
                criterios={solicitud.criterios}
                experienciaMin={solicitud.experiencia_min}
              />
              <div style={{ fontSize: 11, color: 'var(--muted-2)', marginTop: 6 }}>
                {formatearFecha(solicitud.created_at)} · Creada por {solicitud.usuario_nombre}
              </div>
            </div>

            <div style={{ fontSize: 12 }}>
              {solicitud.total_candidatos != null && <div>{solicitud.total_candidatos} candidatos</div>}
              {solicitud.mejor_afinidad != null && (
                <div style={{ color: 'var(--muted)' }}>{solicitud.mejor_afinidad}% mejor afinidad</div>
              )}
              {/* HU-24: al volver a la solicitud se ve cuántos se marcaron para el cliente. */}
              {!!solicitud.total_preseleccionados && (
                <div style={{ color: 'var(--green-tx)', fontWeight: 600 }}>
                  ✓ {textoPreseleccionados(solicitud.total_preseleccionados)}
                </div>
              )}
              {solicitud.estado === 'EN_ANALISIS' && (
                <div style={{ color: 'var(--muted)' }}>Analizando perfiles…</div>
              )}
              {solicitud.total_ejecuciones > 1 && (
                <div style={{ color: 'var(--muted)' }}>{solicitud.total_ejecuciones} ejecuciones</div>
              )}
            </div>

            <EstadoBadge estado={solicitud.estado} />

            <div style={{ display: 'flex', flexDirection: 'column', gap: 8, alignItems: 'flex-end' }}>
              <button className="bm-btn bm-btn-ghost" onClick={() => void duplicar(solicitud.id)}>
                Duplicar
              </button>

              {solicitud.estado === 'PROCESADA' && (
                <>
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

              {solicitud.estado === 'SIN_COINCIDENCIAS' && (
                // HU-23: desde el historial se puede ajustar la búsqueda y volver a intentarlo.
                <>
                  <button
                    className="bm-btn bm-btn-ghost"
                    onClick={() => navegar(`/nueva-busqueda?solicitud=${solicitud.id}`)}
                  >
                    Ajustar criterios
                  </button>
                  <button
                    className="bm-btn bm-btn-dark"
                    onClick={() => navegar(`/resultados/${solicitud.busqueda_id}`)}
                  >
                    Ver resultados →
                  </button>
                </>
              )}

              {solicitud.estado === 'BORRADOR' && (
                <>
                  <button
                    className="bm-btn bm-btn-ghost bm-btn-soft bm-btn-draft-hover"
                    onClick={() => navegar(`/nueva-busqueda?solicitud=${solicitud.id}`)}
                  >
                    Continuar editando →
                  </button>
                  <button
                    className="bm-btn bm-btn-ghost bm-btn-compact bm-btn-delete-hover"
                    onClick={() => void eliminarBorrador(solicitud.id)}
                  >
                    Eliminar
                  </button>
                </>
              )}

              {solicitud.estado === 'ERROR' && solicitud.busqueda_id && solicitud.total_ejecuciones > 1 && (
                // HU-15: si un ajuste falló, las ejecuciones anteriores siguen consultables.
                <button
                  className="bm-btn bm-btn-ghost"
                  onClick={() => navegar(`/resultados/${solicitud.busqueda_id}`)}
                >
                  Ver ejecuciones →
                </button>
              )}

              {solicitud.estado === 'ERROR' && (
                <button
                  className="bm-btn bm-btn-ghost"
                  onClick={() => void reejecutar(solicitud.id)}
                  disabled={reintentando !== null}
                  aria-busy={reintentando === solicitud.id}
                >
                  {reintentando === solicitud.id ? 'Analizando…' : 'Reintentar →'}
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

function textoPreseleccionados(total: number): string {
  return total === 1 ? '1 preseleccionado' : `${total} preseleccionados`
}
