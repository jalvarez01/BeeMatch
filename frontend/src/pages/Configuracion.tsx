import { useEffect, useState } from 'react'

import { apiFetch } from '../api/client'
import {
  guardarConexion,
  obtenerConexion,
  probarConexion,
  probarConexionGuardada,
  type ConexionPayload,
  type Credenciales,
  type PruebaConexion,
  type TipoRepositorio,
} from '../api/repositorio'

interface EstadoIndice {
  total: number
  indexadas: number
  pendientes: number
  no_procesables: number
}

interface Sincronizacion {
  documentos_detectados: number
  documentos_encolados: number
  /** Registrados pero todavía sin indexar, por ejemplo si falta el proveedor de embeddings. */
  documentos_aplazados: number
  mensaje: string
}

interface Parametro {
  clave: string
  valor: string
  descripcion: string | null
}

/** Campos propios de OneDrive: los cuatro de la aplicación registrada y la ruta. */
interface FormularioOneDrive {
  tenant_id: string
  client_id: string
  client_secret: string
  drive_id: string
  carpeta: string
}

/** Campos propios de Google Drive: el JSON de la cuenta de servicio y la carpeta. */
interface FormularioGDrive {
  credenciales_json: string
  carpeta: string
}

const ONEDRIVE_VACIO: FormularioOneDrive = {
  tenant_id: '',
  client_id: '',
  client_secret: '',
  drive_id: '',
  carpeta: '/HojasDeVida',
}

const GDRIVE_VACIO: FormularioGDrive = {
  credenciales_json: '',
  carpeta: '',
}

const ETIQUETA_ORIGEN: Record<TipoRepositorio, string> = {
  ONEDRIVE: 'OneDrive / SharePoint',
  GDRIVE: 'Google Drive',
}

interface AnalisisJson {
  valido: boolean
  client_email: string | null
  error: string | null
}

const JSON_SIN_CARGAR: AnalisisJson = { valido: false, client_email: null, error: null }

/**
 * Validación en el cliente del archivo de la cuenta de servicio: evita enviar
 * al backend un JSON roto o el archivo equivocado (por ejemplo, credenciales
 * de OAuth de escritorio en vez de una cuenta de servicio).
 */
function analizarCredencialesJson(texto: string): AnalisisJson {
  const limpio = texto.trim()
  if (limpio === '') return JSON_SIN_CARGAR

  let datos: unknown
  try {
    datos = JSON.parse(limpio)
  } catch {
    return { valido: false, client_email: null, error: 'El contenido no es un JSON válido.' }
  }

  if (typeof datos !== 'object' || datos === null || Array.isArray(datos)) {
    return {
      valido: false,
      client_email: null,
      error: 'El JSON no tiene la forma del archivo de una cuenta de servicio.',
    }
  }

  const objeto = datos as Record<string, unknown>
  if (objeto.type !== 'service_account') {
    return {
      valido: false,
      client_email: null,
      error: 'El archivo no es de una cuenta de servicio (se esperaba type: "service_account").',
    }
  }

  return {
    valido: true,
    client_email: typeof objeto.client_email === 'string' ? objeto.client_email : null,
    error: null,
  }
}

/** HU-05 (conexión al repositorio), HU-06 (bitácora) y HU-07 (parámetros). */
export default function Configuracion() {
  const [tipo, setTipo] = useState<TipoRepositorio>('ONEDRIVE')
  const [onedrive, setOnedrive] = useState<FormularioOneDrive>(ONEDRIVE_VACIO)
  const [gdrive, setGdrive] = useState<FormularioGDrive>(GDRIVE_VACIO)

  const [tipoGuardado, setTipoGuardado] = useState<TipoRepositorio | null>(null)
  const [secretosGuardados, setSecretosGuardados] = useState<Credenciales>({})
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
        setTipoGuardado(config.configurado ? config.tipo : null)
        setSecretosGuardados(config.credenciales)
        setUltimaValidacion(config.ultima_validacion)
        setDocumentosDetectados(config.documentos_detectados)

        if (!config.configurado || !config.tipo) return

        // Se precargan el origen y los campos no secretos; los secretos solo
        // se muestran enmascarados como placeholder.
        setTipo(config.tipo)
        if (config.tipo === 'ONEDRIVE') {
          setOnedrive({
            tenant_id: config.credenciales.tenant_id ?? '',
            client_id: config.credenciales.client_id ?? '',
            client_secret: '',
            drive_id: config.credenciales.drive_id ?? '',
            carpeta: config.carpeta ?? ONEDRIVE_VACIO.carpeta,
          })
        } else {
          setGdrive({ credenciales_json: '', carpeta: config.carpeta ?? '' })
        }
      })
      .catch((e: Error) => setError(e.message))

    apiFetch<EstadoIndice>('/hojas-vida/estado').then(setIndice).catch(() => undefined)
    apiFetch<Parametro[]>('/configuracion/parametros').then(setParametros).catch(() => undefined)
  }

  useEffect(cargar, [])

  const setOneDrive = <K extends keyof FormularioOneDrive>(campo: K, valor: string) =>
    setOnedrive((previo) => ({ ...previo, [campo]: valor }))

  const setGDrive = <K extends keyof FormularioGDrive>(campo: K, valor: string) =>
    setGdrive((previo) => ({ ...previo, [campo]: valor }))

  /** El origen activo ya tiene credenciales guardadas que el backend reutiliza. */
  const configurado = tipoGuardado !== null
  const reutilizaSecreto = tipoGuardado === tipo
  const secretoEnmascarado = reutilizaSecreto
    ? tipo === 'ONEDRIVE'
      ? secretosGuardados.client_secret ?? null
      : secretosGuardados.credenciales_json ?? null
    : null

  const analisisJson = analizarCredencialesJson(gdrive.credenciales_json)

  const cambiarTipo = (nuevo: TipoRepositorio) => {
    if (nuevo === tipo) return
    setTipo(nuevo)
    // El resultado anterior es de otro origen: dejarlo visible confundiría.
    setPrueba(null)
    setMensaje('')
    setError('')
  }

  const leerArchivoJson = (archivo: File | undefined) => {
    if (!archivo) return
    const lector = new FileReader()
    lector.onload = () => setGDrive('credenciales_json', String(lector.result ?? ''))
    lector.onerror = () => setError('No se pudo leer el archivo seleccionado.')
    lector.readAsText(archivo)
  }

  const camposCompletos =
    tipo === 'ONEDRIVE'
      ? onedrive.tenant_id.trim() !== '' &&
        onedrive.client_id.trim() !== '' &&
        onedrive.drive_id.trim() !== '' &&
        (reutilizaSecreto || onedrive.client_secret.trim() !== '')
      : gdrive.carpeta.trim() !== '' &&
        (analisisJson.valido || (reutilizaSecreto && gdrive.credenciales_json.trim() === ''))

  /** Los secretos vacíos se omiten: el backend reutiliza el valor almacenado. */
  const construirPayload = (): ConexionPayload => {
    if (tipo === 'ONEDRIVE') {
      const credenciales: Credenciales = {
        tenant_id: onedrive.tenant_id.trim(),
        client_id: onedrive.client_id.trim(),
        drive_id: onedrive.drive_id.trim(),
      }
      if (onedrive.client_secret.trim() !== '') credenciales.client_secret = onedrive.client_secret
      return { tipo, carpeta: onedrive.carpeta.trim(), credenciales }
    }

    const credenciales: Credenciales = {}
    if (gdrive.credenciales_json.trim() !== '') {
      credenciales.credenciales_json = gdrive.credenciales_json.trim()
    }
    return { tipo, carpeta: gdrive.carpeta.trim(), credenciales }
  }

  const probar = async () => {
    setProbando(true)
    setPrueba(null)
    setMensaje('')
    setError('')
    try {
      setPrueba(await probarConexion(construirPayload()))
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
      const respuesta = await guardarConexion(construirPayload())
      setPrueba(respuesta.prueba)

      if (respuesta.guardado) {
        setMensaje('Configuración guardada. Las búsquedas usarán esta carpeta como origen.')
        setOneDrive('client_secret', '')
        setGDrive('credenciales_json', '')
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
      const respuesta = await apiFetch<Sincronizacion>('/hojas-vida/sincronizar', { method: 'POST' })
      // El mensaje del backend ya trae el detalle cuando la indexación queda
      // aplazada; el conteo de la cola solo se agrega si hubo algo que encolar.
      setMensaje(
        respuesta.documentos_encolados > 0
          ? `${respuesta.mensaje} (${respuesta.documentos_encolados} documentos en cola)`
          : respuesta.mensaje,
      )
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
            Conexión con el repositorio
          </h2>
          <span className={`bm-badge ${configurado ? 'bm-badge-green' : 'bm-badge-gray'}`}>
            {configurado && tipoGuardado ? `Configurada · ${ETIQUETA_ORIGEN[tipoGuardado]}` : 'Sin configurar'}
          </span>
        </div>

        <p style={{ fontSize: 12, color: 'var(--muted)', margin: '0 0 16px' }}>
          BeeMatch accede en solo lectura. Los documentos no se copian: se consultan desde la
          carpeta que registres aquí.
        </p>

        <div className="bm-field" style={{ marginBottom: 12 }}>
          <label htmlFor="origen">Origen de las hojas de vida</label>
          <select
            id="origen"
            value={tipo}
            onChange={(e) => cambiarTipo(e.target.value as TipoRepositorio)}
          >
            <option value="ONEDRIVE">{ETIQUETA_ORIGEN.ONEDRIVE}</option>
            <option value="GDRIVE">{ETIQUETA_ORIGEN.GDRIVE}</option>
          </select>
        </div>

        {tipo === 'ONEDRIVE' ? (
          <div className="bm-grid2">
            <div className="bm-field">
              <label htmlFor="tenant">Tenant ID</label>
              <input
                id="tenant"
                value={onedrive.tenant_id}
                placeholder="00000000-0000-0000-0000-000000000000"
                onChange={(e) => setOneDrive('tenant_id', e.target.value)}
              />
            </div>

            <div className="bm-field">
              <label htmlFor="clientid">Client ID</label>
              <input
                id="clientid"
                value={onedrive.client_id}
                placeholder="ID de la aplicación registrada"
                onChange={(e) => setOneDrive('client_id', e.target.value)}
              />
            </div>

            <div className="bm-field">
              <label htmlFor="secret">Client Secret</label>
              <input
                id="secret"
                type="password"
                value={onedrive.client_secret}
                placeholder={
                  secretoEnmascarado ? `Guardado: ${secretoEnmascarado}` : 'Valor del secreto'
                }
                onChange={(e) => setOneDrive('client_secret', e.target.value)}
              />
            </div>

            <div className="bm-field">
              <label htmlFor="drive">Drive ID</label>
              <input
                id="drive"
                value={onedrive.drive_id}
                placeholder="Identificador del repositorio"
                onChange={(e) => setOneDrive('drive_id', e.target.value)}
              />
            </div>

            <div className="bm-field" style={{ gridColumn: '1 / -1' }}>
              <label htmlFor="carpeta">Carpeta de hojas de vida</label>
              <input
                id="carpeta"
                value={onedrive.carpeta}
                placeholder="/HojasDeVida"
                onChange={(e) => setOneDrive('carpeta', e.target.value)}
              />
            </div>
          </div>
        ) : (
          <>
            <div className="bm-archivo">
              <label htmlFor="archivo-json">Archivo JSON de la cuenta de servicio</label>
              <input
                id="archivo-json"
                type="file"
                accept=".json,application/json"
                onChange={(e) => leerArchivoJson(e.target.files?.[0])}
              />
              {analisisJson.valido && (
                <span className="ok">
                  ✓ Cuenta de servicio
                  {analisisJson.client_email ? `: ${analisisJson.client_email}` : ' válida'}
                </span>
              )}
              {analisisJson.error && <span className="err">✕ {analisisJson.error}</span>}
              {!analisisJson.valido && !analisisJson.error && secretoEnmascarado && (
                <span style={{ fontSize: 12, color: 'var(--muted-2)' }}>
                  Guardado: {secretoEnmascarado}
                </span>
              )}
            </div>

            <div style={{ marginTop: 12 }}>
              <label htmlFor="json-pegado" className="bm-label">
                O pega aquí el contenido del archivo
              </label>
              <textarea
                id="json-pegado"
                className="bm-textarea"
                value={gdrive.credenciales_json}
                placeholder='{ "type": "service_account", "client_email": "…", … }'
                onChange={(e) => setGDrive('credenciales_json', e.target.value)}
              />
            </div>

            <div className="bm-field" style={{ marginTop: 12 }}>
              <label htmlFor="carpeta-gdrive">ID de la carpeta de Drive</label>
              <input
                id="carpeta-gdrive"
                value={gdrive.carpeta}
                placeholder="1AbC2dEfGhIjKlMnOpQrStUvWxYz"
                onChange={(e) => setGDrive('carpeta', e.target.value)}
              />
            </div>

            <p style={{ fontSize: 12, color: 'var(--muted)', margin: '12px 0 0' }}>
              Comparte la carpeta de Drive con el correo de la cuenta de servicio en modo{' '}
              <strong>Lector</strong>. Sin ese permiso la conexión falla aunque las credenciales
              sean válidas.
            </p>
          </>
        )}

        {reutilizaSecreto && (
          <p style={{ fontSize: 11, color: 'var(--muted-2)', margin: '12px 0 0' }}>
            {tipo === 'ONEDRIVE'
              ? 'El secreto está almacenado cifrado. Déjalo vacío si solo quieres cambiar la ruta.'
              : 'El JSON está almacenado cifrado. Déjalo vacío si solo quieres cambiar la carpeta.'}
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
