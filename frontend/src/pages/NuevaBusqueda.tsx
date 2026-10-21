import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { ejecutarBusqueda } from '../api/busquedas'
import { listarRoles } from '../api/candidatos'
import { actualizarSolicitud, crearSolicitud, obtenerSolicitud } from '../api/solicitudes'
import { IconSpark } from '../components/Icons'
import type { Criterio, SolicitudPayload, TipoCriterio } from '../types'

const DESCRIPCION_MIN = 15
const DESCRIPCION_MAX = 1000
const EXPERIENCIA_MAX = 50
const MENSAJE_DESCRIPCION_CORTA = `La descripción es muy corta. Describe el perfil con más detalle (mínimo ${DESCRIPCION_MIN} caracteres).`
const MENSAJE_DESCRIPCION_VACIA = 'Falta la descripción del perfil. Cuéntale a BeeMatch qué perfil necesitas.'
const MENSAJE_ROL_VACIO = 'Falta el rol requerido. Escríbelo o elige uno de la lista.'
const MENSAJE_EXPERIENCIA = `Ingresa solo números enteros positivos (de 1 a ${EXPERIENCIA_MAX} años).`

/** HU-10: campos que se validan antes de buscar, en el orden del formulario. */
type CampoValidado = 'descripcion' | 'rol' | 'experiencia'
type ErroresSolicitud = Partial<Record<CampoValidado, string>>
const ORDEN_CAMPOS: CampoValidado[] = ['descripcion', 'rol', 'experiencia']

/** HU-08, HU-09, HU-10, HU-11, HU-12, HU-15. */
export default function NuevaBusqueda() {
  const navegar = useNavigate()
  const [params] = useSearchParams()
  const solicitudId = params.get('solicitud')

  const [descripcion, setDescripcion] = useState('')
  const [errores, setErrores] = useState<ErroresSolicitud>({})
  const campoDescripcion = useRef<HTMLTextAreaElement>(null)
  const campoRol = useRef<HTMLInputElement>(null)
  const campoExperiencia = useRef<HTMLInputElement>(null)
  const [cliente, setCliente] = useState('')
  const [proyecto, setProyecto] = useState('')
  const [rol, setRol] = useState('')
  const [experiencia, setExperiencia] = useState<number | ''>('')
  const [tecnologias, setTecnologias] = useState<string[]>([])
  const [idiomas, setIdiomas] = useState<string[]>([])
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [roles, setRoles] = useState<string[]>([])

  // Los roles salen de lo que la IA identificó en las hojas de vida: al
  // cargar perfiles de un área nueva, aparecen aquí sin tocar código.
  useEffect(() => {
    listarRoles()
      .then((disponibles) => setRoles(disponibles.map((r) => r.nombre)))
      .catch(() => setRoles([]))
  }, [])

  // HU-11 / HU-14 / HU-15: precarga de un borrador o de una solicitud duplicada.
  useEffect(() => {
    if (!solicitudId) return
    obtenerSolicitud(solicitudId)
      .then((solicitud) => {
        setDescripcion(solicitud.descripcion_libre)
        setCliente(solicitud.cliente_nombre ?? '')
        setProyecto(solicitud.proyecto_nombre ?? '')
        setRol(solicitud.rol_buscado ?? '')
        setExperiencia(solicitud.experiencia_min ?? '')
        setTecnologias(
          solicitud.criterios.filter((c) => c.tipo !== 'IDIOMA').map((c) => c.valor),
        )
        setIdiomas(solicitud.criterios.filter((c) => c.tipo === 'IDIOMA').map((c) => c.valor))
      })
      .catch((e: Error) => setError(e.message))
  }, [solicitudId])

  const construirPayload = (): SolicitudPayload => {
    const criterios: Criterio[] = [
      ...tecnologias.map((valor) => criterio(valor, 'TECNOLOGIA')),
      ...idiomas.map((valor) => criterio(valor, 'IDIOMA')),
    ]
    return {
      descripcion_libre: descripcion,
      rol_buscado: rol || null,
      experiencia_min: experiencia === '' ? null : experiencia,
      cliente: cliente || null,
      proyecto: proyecto || null,
      criterios,
    }
  }

  /**
   * HU-10: marca los campos con error y lleva el foco al primero. Un borrador
   * puede quedar incompleto; una búsqueda necesita rol y descripción.
   */
  const validar = (paraBuscar: boolean): boolean => {
    const encontrados = validarSolicitud(descripcion, rol, experiencia, paraBuscar)
    setErrores(encontrados)
    const primero = ORDEN_CAMPOS.find((campo) => encontrados[campo])
    if (!primero) return true
    const referencias = { descripcion: campoDescripcion, rol: campoRol, experiencia: campoExperiencia }
    referencias[primero].current?.focus()
    return false
  }

  const marcarError = (campo: CampoValidado, mensaje?: string) =>
    setErrores((actuales) => ({ ...actuales, [campo]: mensaje }))

  const atributosDeError = (campo: CampoValidado) =>
    errores[campo] ? { 'aria-invalid': true, 'aria-describedby': `${campo}-error` } : {}

  const guardarBorrador = async () => {
    setError('')
    if (!validar(false)) return
    try {
      const solicitud = solicitudId
        ? await actualizarSolicitud(solicitudId, construirPayload())
        : await crearSolicitud(construirPayload())
      navegar(`/historial?guardada=${solicitud.id}`)
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const buscar = async () => {
    setError('')
    if (!validar(true)) return
    setEnviando(true)
    try {
      const solicitud = solicitudId
        ? await actualizarSolicitud(solicitudId, construirPayload())
        : await crearSolicitud(construirPayload())
      const busqueda = await ejecutarBusqueda(solicitud.id)
      navegar(`/resultados/${busqueda.id}`)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <>
      <h1 className="bm-h1">Nueva búsqueda con IA</h1>
      <p className="bm-sub">
        Describe el perfil que necesitas y BeeMatch encontrará los candidatos con mayor afinidad.
      </p>

      {error && <div className="bm-alert bm-alert-error">{error}</div>}

      <div className="bm-tip" style={{ marginBottom: 18 }}>
        <div
          className="bm-h3"
          style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}
        >
          <IconSpark /> Describe lo que estás buscando
        </div>
        <p style={{ fontSize: 12, color: 'var(--muted)', margin: '0 0 12px' }}>
          Puedes escribirlo de forma natural. La IA identificará automáticamente habilidades,
          experiencia y requisitos.
        </p>
        <textarea
          ref={campoDescripcion}
          className="bm-textarea"
          maxLength={DESCRIPCION_MAX}
          value={descripcion}
          disabled={enviando}
          onChange={(e) => {
            setDescripcion(e.target.value)
            marcarError('descripcion')
          }}
          aria-required="true"
          data-error={errores.descripcion ? 'true' : undefined}
          {...atributosDeError('descripcion')}
          placeholder="Ej. Necesito un desarrollador Backend Java Senior con mínimo 5 años de experiencia, conocimientos en Spring Boot y AWS, experiencia en el sector bancario e inglés B2."
        />
        <MensajeError id="descripcion-error" mensaje={errores.descripcion} />
        <div className="bm-count">{descripcion.length}/{DESCRIPCION_MAX}</div>
      </div>

      <h2 className="bm-h2">Detalles de la solicitud</h2>
      <p style={{ fontSize: 12, color: 'var(--muted)', margin: '0 0 14px' }}>
        Agrega contexto para mejorar la precisión de las recomendaciones.
      </p>

      <div className="bm-grid2">
        <div className="bm-field">
          <label htmlFor="cliente">Cliente</label>
          <input
            id="cliente"
            placeholder="Seleccionar cliente"
            value={cliente}
            disabled={enviando}
            onChange={(e) => setCliente(e.target.value)}
          />
        </div>

        <div className="bm-field">
          <label htmlFor="proyecto">Proyecto</label>
          <input
            id="proyecto"
            placeholder="Nombre del proyecto"
            value={proyecto}
            disabled={enviando}
            onChange={(e) => setProyecto(e.target.value)}
          />
        </div>

        <div>
          <div className="bm-field" data-error={errores.rol ? 'true' : undefined}>
            <label htmlFor="rol">Rol requerido</label>
            {/*
              Texto libre, no una lista cerrada: el rol no filtra en SQL, se suma
              a la consulta que resuelven los embeddings y el re-ranking, así que
              acepta cualquier cargo. La lista solo sugiere los que la IA ya
              identificó en las hojas de vida del repositorio.
            */}
            <input
              id="rol"
              ref={campoRol}
              list="roles-sugeridos"
              placeholder="Escribir o elegir rol"
              value={rol}
              disabled={enviando}
              onChange={(e) => {
                setRol(e.target.value)
                marcarError('rol')
              }}
              aria-required="true"
              {...atributosDeError('rol')}
            />
            <datalist id="roles-sugeridos">
              {roles.map((r) => (
                <option key={r} value={r} />
              ))}
            </datalist>
          </div>
          <MensajeError id="rol-error" mensaje={errores.rol} />
        </div>

        <div>
          <div className="bm-field" data-error={errores.experiencia ? 'true' : undefined}>
            <label htmlFor="experiencia">Experiencia mínima</label>
            {/*
              HU-10: solo enteros positivos. Lo que no es dígito no entra al
              campo y el aviso explica por qué, en vez de ignorar la tecla.
            */}
            <input
              id="experiencia"
              ref={campoExperiencia}
              inputMode="numeric"
              maxLength={2}
              placeholder="Años, ej. 5"
              value={experiencia}
              disabled={enviando}
              onChange={(e) => {
                const digitos = e.target.value.replace(/\D/g, '')
                const valor = digitos === '' ? '' : Number(digitos)
                setExperiencia(valor)
                const valido = digitos === e.target.value && experienciaValida(valor)
                marcarError('experiencia', valido ? undefined : MENSAJE_EXPERIENCIA)
              }}
              {...atributosDeError('experiencia')}
            />
          </div>
          <MensajeError id="experiencia-error" mensaje={errores.experiencia} />
        </div>

        <CampoChips
          id="tecnologias"
          etiqueta="Tecnologías y habilidades"
          placeholder="Buscar tecnología…"
          valores={tecnologias}
          onCambio={setTecnologias}
          deshabilitado={enviando}
        />

        <CampoChips
          id="idiomas"
          etiqueta="Idiomas"
          placeholder="Agregar idioma…"
          valores={idiomas}
          onCambio={setIdiomas}
          deshabilitado={enviando}
        />
      </div>

      <div className="bm-tip" style={{ margin: '18px 0' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, fontWeight: 600 }}>
          <IconSpark /> Consejo de BeeMatch
        </div>
        <p style={{ fontSize: 11, color: 'var(--muted)', margin: '4px 0 0' }}>
          Mientras más contexto proporciones sobre el proyecto y las habilidades requeridas, más
          precisas serán las recomendaciones.
        </p>
      </div>

      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10 }}>
        <button className="bm-btn bm-btn-soft" onClick={guardarBorrador} disabled={enviando}>
          Guardar borrador
        </button>
        <button className="bm-btn bm-btn-primary" onClick={buscar} disabled={enviando}>
          {enviando ? 'Analizando…' : 'Buscar candidatos con IA'}
        </button>
      </div>
    </>
  )
}

function criterio(valor: string, tipo: TipoCriterio): Criterio {
  return { tipo, valor, obligatorio: false, peso: 1 }
}

function descripcionMuyCorta(descripcion: string): boolean {
  const texto = descripcion.trim()
  return texto.length > 0 && texto.length < DESCRIPCION_MIN
}

/** HU-10: vacío es válido (no exige mínimo); si hay valor, entero entre 1 y el máximo. */
function experienciaValida(experiencia: number | ''): boolean {
  return experiencia === '' || (Number.isInteger(experiencia) && experiencia > 0 && experiencia <= EXPERIENCIA_MAX)
}

function validarSolicitud(
  descripcion: string,
  rol: string,
  experiencia: number | '',
  paraBuscar: boolean,
): ErroresSolicitud {
  const errores: ErroresSolicitud = {}
  if (paraBuscar) {
    if (!descripcion.trim()) errores.descripcion = MENSAJE_DESCRIPCION_VACIA
    else if (descripcionMuyCorta(descripcion)) errores.descripcion = MENSAJE_DESCRIPCION_CORTA
    if (!rol.trim()) errores.rol = MENSAJE_ROL_VACIO
  }
  if (!experienciaValida(experiencia)) errores.experiencia = MENSAJE_EXPERIENCIA
  return errores
}

function MensajeError({ id, mensaje }: { id: string; mensaje?: string }) {
  if (!mensaje) return null
  return (
    <div id={id} className="bm-error" role="alert">
      {mensaje}
    </div>
  )
}

function CampoChips({
  id,
  etiqueta,
  placeholder,
  valores,
  onCambio,
  deshabilitado,
}: {
  id: string
  etiqueta: string
  placeholder: string
  valores: string[]
  onCambio: (valores: string[]) => void
  deshabilitado?: boolean
}) {
  const agregar = (evento: React.KeyboardEvent<HTMLInputElement>) => {
    if (evento.key !== 'Enter') return
    evento.preventDefault()
    const entrada = evento.currentTarget
    const valor = entrada.value.trim()
    if (valor && !valores.includes(valor)) onCambio([...valores, valor])
    entrada.value = ''
  }

  return (
    <div className="bm-field-chips">
      <div className="bm-field">
        <label htmlFor={id}>{etiqueta}</label>
        <input id={id} placeholder={placeholder} onKeyDown={agregar} disabled={deshabilitado} />
      </div>
      {valores.length > 0 && (
        <div className="bm-chips">
          {valores.map((valor) => (
            <span className="bm-chip" key={valor}>
              {valor}
              <button
                onClick={() => onCambio(valores.filter((v) => v !== valor))}
                aria-label={`Quitar ${valor}`}
                disabled={deshabilitado}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
