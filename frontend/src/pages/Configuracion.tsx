import { useEffect, useState } from 'react'

import { apiFetch } from '../api/client'
import {
  guardarConexion,
  obtenerConexion,
  probarConexion,
  probarConexionGuardada,
  type ConexionPayload,
  type PruebaConexion,
} from '../api/onedrive'

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

const FORMULARIO_VACIO: ConexionPayload = {
  tenant_id: '',
  client_id: '',
  client_secret: '',
  drive_id: '',
  carpeta_cv: '/HojasDeVida',
}

/** HU-05 (conexión a OneDrive), HU-06 (bitácora) y HU-07 (parámetros). */
export default function Configuracion() {
  const [form, setForm] = useState<ConexionPayload>(FORMULARIO_VACIO)
  const [configurado, setConfigurado] = useState(false)
  const [secretoGuardado, setSecretoGuardado] = useState<string | null>(null)
  const [ultimaValidacion, setUltimaValidacion] = useState<string | null>(null)
  const [documentosDetectados, setDocumentosDetectados] = useState<number | null>(null)

  const [prueba, setPrueba] = useState<PruebaConexion | null>(null)
  const [probando, setProbando] = useState(false)
  const [guardando, setGuardando] = useState(false)
  const [mensaje, setMensaje] = useState('')
  const [error, setError] = useState('')

  const [indice, setIndice] = useState<EstadoIndice | null>(null)
  const [parametros, setParametros] = useState<Parametro[]>([])
  const [sincronizando, setSincronizando] = useState(false)

  const cargar = () => {
    obtenerConexion()
      .then((config) => {
        setConfigurado(config.configurado)
        setSecretoGuardado(config.client_secret_enmascarado)
        setUltimaValidacion(config.ultima_validacion)
        setDocumentosDetectados(config.documentos_detectados)
        if (config.configurado) {
          setForm({
            tenant_id: config.tenant_id ?? '',
            client_id: config.client_id ?? '',
            client_secret: '',
            drive_id: config.drive_id ?? '',
            carpeta_cv: config.carpeta_cv ?? '/HojasDeVida',
          })
        }
      })
      .catch((e: Error) => setError(e.message))

    apiFetch<EstadoIndice>('/hojas-vida/estado').then(setIndice).catch(() => undefined)
    apiFetch<Parametro[]>('/configuracion/parametros').then(setParametros).catch(() => undefined)
  }

  useEffect(cargar, [])

  const set = <K extends keyof ConexionPayload>(campo: K, valor: ConexionPayload[K]) =>
    setForm((previo) => ({ ...previo, [campo]: valor }))

  const camposCompletos =
    form.tenant_id.trim() !== '' &&
    form.client_id.trim() !== '' &&
    form.drive_id.trim() !== '' &&
    (configurado || (form.client_secret ?? '').trim() !== '')

  const probar = async () => {
    setProbando(true)
    setPrueba(null)
    setMensaje('')
    setError('')
    try {
      setPrueba(await probarConexion(form))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setProbando(false)
    }
  }

  const revalidar = async () => {
    setProbando(true)
    setPrueba(null)
    try {
      const resultado = await probarConexionGuardada()
      setPrueba(resultado)
      if (resultado.exito) setDocumentosDetectados(resultado.documentos_detectados)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setProbando(false)
    }
  }

  const guardar = async () => {
    setGuardando(true)
    setPrueba(null)
    setMensaje('')
    setError('')
    try {
      const respuesta = await guardarConexion(form)
      setPrueba(respuesta.prueba)

      if (respuesta.guardado) {
        setMensaje('Configuración guardada. Las búsquedas usarán esta carpeta como origen.')
        set('client_secret', '')
        cargar()
      }
      // Si no se guardó, la configuración anterior sigue intacta y el motivo
      // del error queda visible en el bloque de resultado.
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setGuardando(false)
    }
  }

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
      <p className="bm-sub">Conexión al repositorio de hojas de vida y parámetros de recomendación.</p>

      {error && <div className="bm-alert bm-alert-error">{error}</div>}
      {mensaje && <div className="bm-alert bm-alert-info">{mensaje}</div>}

      {/* ---------- HU-05 ---------- */}
      <div className="bm-card">
        <div className="bm-row-between" style={{ marginBottom: 4 }}>
          <h2 className="bm-h2" style={{ margin: 0 }}>
            Conexión con OneDrive
          </h2>
          <span className={`bm-badge ${configurado ? 'bm-badge-green' : 'bm-badge-gray'}`}>
            {configurado ? 'Configurada' : 'Sin configurar'}
          </span>
        </div>

        <p style={{ fontSize: 12, color: 'var(--muted)', margin: '0 0 16px' }}>
          BeeMatch accede en solo lectura. Los documentos no se copian: se consultan desde la
          carpeta que registres aquí.
        </p>

        <div className="bm-grid2">
          <div className="bm-field">
            <label htmlFor="tenant">Tenant ID</label>
            <input
              id="tenant"
              value={form.tenant_id}
              placeholder="00000000-0000-0000-0000-000000000000"
              onChange={(e) => set('tenant_id', e.target.value)}
            />
          </div>

          <div className="bm-field">
            <label htmlFor="clientid">Client ID</label>
            <input
              id="clientid"
              value={form.client_id}
              placeholder="ID de la aplicación registrada"
              onChange={(e) => set('client_id', e.target.value)}
            />
          </div>

          <div className="bm-field">
            <label htmlFor="secret">Client Secret</label>
            <input
              id="secret"
              type="password"
              value={form.client_secret ?? ''}
              placeholder={secretoGuardado ? `Guardado: ${secretoGuardado}` : 'Valor del secreto'}
              onChange={(e) => set('client_secret', e.target.value)}
            />
          </div>

          <div className="bm-field">
            <label htmlFor="drive">Drive ID</label>
            <input
              id="drive"
              value={form.drive_id}
              placeholder="Identificador del repositorio"
              onChange={(e) => set('drive_id', e.target.value)}
            />
          </div>

          <div className="bm-field" style={{ gridColumn: '1 / -1' }}>
            <label htmlFor="carpeta">Carpeta de hojas de vida</label>
            <input
              id="carpeta"
              value={form.carpeta_cv}
              placeholder="/HojasDeVida"
              onChange={(e) => set('carpeta_cv', e.target.value)}
            />
          </div>
        </div>

        {configurado && (
          <p style={{ fontSize: 11, color: 'var(--muted-2)', margin: '12px 0 0' }}>
            El secreto está almacenado cifrado. Déjalo vacío si solo quieres cambiar la ruta.
          </p>
        )}

        {/* Resultado de la prueba (HU-05: éxito con conteo, o motivo del error) */}
        {prueba && (
          <div
            className={`bm-alert ${prueba.exito ? 'bm-alert-ok' : 'bm-alert-error'}`}
            style={{ marginTop: 16, marginBottom: 0 }}
            role="status"
            aria-live="polite"
          >
            <strong>{prueba.exito ? '✓ ' : '✕ '}{prueba.mensaje}</strong>
            {prueba.detalle && (
              <div style={{ marginTop: 6, fontSize: 12 }}>{prueba.detalle}</div>
            )}
            {!prueba.exito && configurado && (
              <div style={{ marginTop: 6, fontSize: 12 }}>
                La configuración anterior no fue modificada.
              </div>
            )}
          </div>
        )}

        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 16 }}>
          <button className="bm-btn bm-btn-ghost" onClick={probar} disabled={probando || !camposCompletos}>
            {probando ? 'Probando…' : 'Probar conexión'}
          </button>
          <button className="bm-btn bm-btn-primary" onClick={guardar} disabled={guardando || !camposCompletos}>
            {guardando ? 'Validando…' : 'Guardar configuración'}
          </button>
        </div>
      </div>

      {/* ---------- Estado del repositorio ---------- */}
      <div className="bm-card">
        <div className="bm-row-between">
          <div>
            <h2 className="bm-h2" style={{ margin: 0 }}>
              Estado del repositorio
            </h2>
            {ultimaValidacion && (
              <p style={{ fontSize: 11, color: 'var(--muted-2)', margin: '4px 0 0' }}>
                Última validación: {new Date(ultimaValidacion).toLocaleString('es-CO')}
                {documentosDetectados != null && ` · ${documentosDetectados} documentos detectados`}
              </p>
            )}
          </div>
          <div style={{ display: 'flex', gap: 10 }}>
            <button className="bm-btn bm-btn-ghost" onClick={revalidar} disabled={!configurado || probando}>
              Revalidar
            </button>
            <button
              className="bm-btn bm-btn-primary"
              onClick={sincronizar}
              disabled={!configurado || sincronizando}
            >
              {sincronizando ? 'Sincronizando…' : 'Sincronizar ahora'}
            </button>
          </div>
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

      {/* ---------- HU-07 ---------- */}
      <div className="bm-card">
        <h2 className="bm-h2">Parámetros de recomendación</h2>
        <p style={{ fontSize: 12, color: 'var(--muted)', margin: '0 0 14px' }}>
          Cambian el comportamiento del motor sin necesidad de desplegar.
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
