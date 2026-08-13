import { useEffect, useState } from 'react'

import { apiFetch } from '../api/client'

interface EstadoIndice {
  total: number
  indexadas: number
  pendientes: number
  no_procesables: number
}

interface Parametro {
  clave: string
  valor: string
  descripcion: string | null
}

/** HU-05, HU-07: conexión a OneDrive y parámetros del motor. Solo administrador. */
export default function Configuracion() {
  const [indice, setIndice] = useState<EstadoIndice | null>(null)
  const [parametros, setParametros] = useState<Parametro[]>([])
  const [mensaje, setMensaje] = useState('')
  const [error, setError] = useState('')
  const [sincronizando, setSincronizando] = useState(false)

  const cargar = () => {
    apiFetch<EstadoIndice>('/hojas-vida/estado').then(setIndice).catch(() => undefined)
    apiFetch<Parametro[]>('/configuracion/parametros')
      .then(setParametros)
      .catch((e: Error) => setError(e.message))
  }

  useEffect(cargar, [])

  const sincronizar = async () => {
    setSincronizando(true)
    setError('')
    setMensaje('')
    try {
      const respuesta = await apiFetch<{ documentos_encolados: number; mensaje: string }>(
        '/hojas-vida/sincronizar',
        { method: 'POST' },
      )
      setMensaje(`${respuesta.mensaje} (${respuesta.documentos_encolados} documentos en cola)`)
      cargar()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setSincronizando(false)
    }
  }

  const guardarParametro = async (clave: string, valor: string) => {
    await apiFetch(`/configuracion/parametros/${clave}`, {
      method: 'PUT',
      body: JSON.stringify({ valor }),
    })
    setMensaje('Parámetro actualizado.')
  }

  return (
    <>
      <h1 className="bm-h1">Configuración</h1>
      <p className="bm-sub">Repositorio de hojas de vida y parámetros de recomendación.</p>

      {error && <div className="bm-alert bm-alert-error">{error}</div>}
      {mensaje && <div className="bm-alert bm-alert-info">{mensaje}</div>}

      <div className="bm-card">
        <div className="bm-row-between">
          <h2 className="bm-h2" style={{ margin: 0 }}>
            Repositorio de OneDrive
          </h2>
          <button className="bm-btn bm-btn-primary" onClick={sincronizar} disabled={sincronizando}>
            {sincronizando ? 'Sincronizando…' : 'Sincronizar ahora'}
          </button>
        </div>

        <div className="bm-kpis" style={{ marginBottom: 0 }}>
          <div className="bm-kpi">
            <div className="l">Documentos</div>
            <div className="n">{indice?.total ?? '—'}</div>
          </div>
          <div className="bm-kpi">
            <div className="l">Indexadas</div>
            <div className="n">{indice?.indexadas ?? '—'}</div>
          </div>
          <div className="bm-kpi">
            <div className="l">Pendientes</div>
            <div className="n">{indice?.pendientes ?? '—'}</div>
          </div>
          <div className="bm-kpi">
            <div className="l">No procesables</div>
            <div className="n">{indice?.no_procesables ?? '—'}</div>
          </div>
        </div>
      </div>

      <div className="bm-card">
        <h2 className="bm-h2">Parámetros de recomendación</h2>
        <p style={{ fontSize: 12, color: 'var(--muted)', margin: '0 0 14px' }}>
          Estos valores cambian el comportamiento del motor sin necesidad de desplegar.
        </p>

        {parametros.map((parametro) => (
          <div className="bm-field" key={parametro.clave} style={{ marginBottom: 10 }}>
            <label htmlFor={parametro.clave}>{parametro.clave}</label>
            <input
              id={parametro.clave}
              defaultValue={parametro.valor}
              onBlur={(e) => void guardarParametro(parametro.clave, e.target.value)}
            />
          </div>
        ))}
      </div>
    </>
  )
}
