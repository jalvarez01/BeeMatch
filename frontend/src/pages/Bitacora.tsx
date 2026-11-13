import { useEffect, useState } from 'react'

import { consultarBitacora } from '../api/bitacora'
import type { EventoBitacora } from '../api/bitacora'
import { listarUsuarios } from '../api/usuarios'
import type { Rol, Usuario } from '../types'

const POR_PAGINA = 20

const ETIQUETA_ROL: Record<Rol, string> = {
  SUPERADMINISTRADOR: 'Superadministrador',
  ADMINISTRADOR: 'Administrador',
  COORDINADOR: 'Coordinador',
  DIRECTOR: 'Director',
}

const ETIQUETA_ACCION: Record<string, string> = {
  LOGIN: 'Inicio de sesión',
  LOGOUT: 'Cierre de sesión',
  SOLICITUD_CREADA: 'Solicitud creada',
  BUSQUEDA_EJECUTADA: 'Búsqueda de candidatos',
  PRESELECCION: 'Preselección',
  EXPORTACION: 'Exportación',
  CONFIG_CAMBIADA: 'Configuración cambiada',
  SINCRONIZACION: 'Sincronización',
  ERROR_SERVICIO: 'Error de servicio',
}

function fechaYHora(iso: string | null): { fecha: string; hora: string } {
  if (!iso) return { fecha: '-', hora: '-' }
  const momento = new Date(iso)
  return {
    fecha: momento.toLocaleDateString('es-CO'),
    hora: momento.toLocaleTimeString('es-CO', { hour12: false }),
  }
}

/** HU-06: bitácora de actividad, con filtros por usuario y por fechas. */
export default function Bitacora() {
  const [usuarios, setUsuarios] = useState<Usuario[]>([])
  const [usuarioId, setUsuarioId] = useState('')
  const [fechaDesde, setFechaDesde] = useState('')
  const [fechaHasta, setFechaHasta] = useState('')
  // Los filtros se aplican al pulsar "Filtrar", no a cada tecla.
  const [aplicados, setAplicados] = useState({ usuarioId: '', fechaDesde: '', fechaHasta: '' })
  const [pagina, setPagina] = useState(1)

  const [eventos, setEventos] = useState<EventoBitacora[]>([])
  const [total, setTotal] = useState(0)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [errorFechas, setErrorFechas] = useState('')

  useEffect(() => {
    listarUsuarios()
      .then(setUsuarios)
      .catch(() => undefined)
  }, [])

  // `cargando` se activa donde cambia la consulta (filtrar, limpiar, paginar),
  // no dentro del efecto, para no encadenar renders.
  useEffect(() => {
    let vigente = true
    consultarBitacora({
      usuarioId: aplicados.usuarioId || undefined,
      fechaDesde: aplicados.fechaDesde || undefined,
      fechaHasta: aplicados.fechaHasta || undefined,
      limite: POR_PAGINA,
      desplazamiento: (pagina - 1) * POR_PAGINA,
    })
      .then((respuesta) => {
        if (!vigente) return
        setEventos(respuesta.items)
        setTotal(respuesta.total)
        setError('')
      })
      .catch((e: Error) => {
        if (vigente) setError(e.message)
      })
      .finally(() => {
        if (vigente) setCargando(false)
      })
    return () => {
      vigente = false
    }
  }, [aplicados, pagina])

  const irAPagina = (numero: number) => {
    setCargando(true)
    setPagina(numero)
  }

  const filtrar = (evento: React.FormEvent) => {
    evento.preventDefault()
    if (fechaDesde && fechaHasta && fechaDesde > fechaHasta) {
      setErrorFechas('La fecha inicial no puede ser posterior a la fecha final.')
      return
    }
    setErrorFechas('')
    setCargando(true)
    setPagina(1)
    setAplicados({ usuarioId, fechaDesde, fechaHasta })
  }

  const limpiar = () => {
    setUsuarioId('')
    setFechaDesde('')
    setFechaHasta('')
    setErrorFechas('')
    setCargando(true)
    setPagina(1)
    setAplicados({ usuarioId: '', fechaDesde: '', fechaHasta: '' })
  }

  const paginas = Math.max(1, Math.ceil(total / POR_PAGINA))

  return (
    <>
      <h1 className="bm-h1">Bitácora de actividad</h1>
      <p className="bm-sub">
        Registro de quién hizo qué y cuándo. Los más recientes aparecen primero.
      </p>

      {error && (
        <div className="bm-alert bm-alert-error" role="alert">
          {error}
        </div>
      )}

      <form className="bm-card" onSubmit={filtrar} aria-label="Filtros de la bitácora">
        <div className="bm-bit-filtros">
          <div className="bm-field">
            <label htmlFor="bit-usuario">Usuario</label>
            <select
              id="bit-usuario"
              value={usuarioId}
              onChange={(e) => setUsuarioId(e.target.value)}
            >
              <option value="">Todos</option>
              {usuarios.map((usuario) => (
                <option key={usuario.id} value={usuario.id}>
                  {usuario.nombre}
                </option>
              ))}
            </select>
          </div>

          <div className="bm-field" data-error={errorFechas ? 'true' : undefined}>
            <label htmlFor="bit-desde">Desde</label>
            <input
              id="bit-desde"
              type="date"
              value={fechaDesde}
              onChange={(e) => setFechaDesde(e.target.value)}
            />
          </div>

          <div className="bm-field" data-error={errorFechas ? 'true' : undefined}>
            <label htmlFor="bit-hasta">Hasta</label>
            <input
              id="bit-hasta"
              type="date"
              value={fechaHasta}
              onChange={(e) => setFechaHasta(e.target.value)}
            />
          </div>

          <div className="bm-bit-botones">
            <button type="submit" className="bm-btn bm-btn-primary">
              Filtrar
            </button>
            <button type="button" className="bm-btn bm-btn-ghost" onClick={limpiar}>
              Limpiar
            </button>
          </div>
        </div>
        {errorFechas && (
          <p className="bm-error" role="alert">
            {errorFechas}
          </p>
        )}
      </form>

      <div className="bm-card">
        <div className="bm-row-between" style={{ marginBottom: 8 }}>
          <h2 className="bm-h2" style={{ margin: 0 }}>
            Eventos
          </h2>
          <span style={{ fontSize: 12, color: 'var(--muted)' }}>
            {total} {total === 1 ? 'registro' : 'registros'}
          </span>
        </div>

        <div className="bm-bit-row bm-bit-head" aria-hidden="true">
          <span>Fecha</span>
          <span>Hora</span>
          <span>Usuario</span>
          <span>Rol</span>
          <span>Acción</span>
        </div>

        {cargando && <p style={{ fontSize: 13, color: 'var(--muted)' }}>Cargando…</p>}

        {!cargando && eventos.length === 0 && (
          <p style={{ fontSize: 13, color: 'var(--muted)', padding: '12px 4px' }}>
            No hay eventos para los filtros elegidos.
          </p>
        )}

        {!cargando &&
          eventos.map((evento) => {
            const { fecha, hora } = fechaYHora(evento.created_at)
            return (
              <div className="bm-bit-row" key={evento.id}>
                <span>{fecha}</span>
                <span>{hora}</span>
                <span>
                  <b>{evento.usuario_nombre ?? 'Sistema'}</b>
                  {evento.usuario_correo && (
                    <span className="bm-bit-sub">{evento.usuario_correo}</span>
                  )}
                </span>
                <span>{evento.rol ? ETIQUETA_ROL[evento.rol] : '-'}</span>
                <span>
                  {ETIQUETA_ACCION[evento.accion] ?? evento.accion}
                  {evento.detalle && <span className="bm-bit-sub">{evento.detalle}</span>}
                </span>
              </div>
            )
          })}

        {paginas > 1 && (
          <div className="bm-pager">
            <button
              onClick={() => irAPagina(Math.max(1, pagina - 1))}
              disabled={pagina === 1}
              aria-label="Anterior"
            >
              ←
            </button>
            <span style={{ fontSize: 12, color: 'var(--muted)' }}>
              Página {pagina} de {paginas}
            </span>
            <button
              onClick={() => irAPagina(Math.min(paginas, pagina + 1))}
              disabled={pagina === paginas}
              aria-label="Siguiente"
            >
              →
            </button>
          </div>
        )}
      </div>
    </>
  )
}
