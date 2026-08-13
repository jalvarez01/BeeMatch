import { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { ejecutarBusqueda } from '../api/busquedas'
import { actualizarSolicitud, crearSolicitud, obtenerSolicitud } from '../api/solicitudes'
import { IconSpark } from '../components/Icons'
import type { Criterio, SolicitudPayload, TipoCriterio } from '../types'

const ROLES = ['Backend Developer', 'Frontend Developer', 'Data Engineer', 'QA Automation']
const EXPERIENCIAS = [1, 3, 5, 8]

/** HU-08, HU-09, HU-10, HU-11, HU-12, HU-15. */
export default function NuevaBusqueda() {
  const navegar = useNavigate()
  const [params] = useSearchParams()
  const solicitudId = params.get('solicitud')

  const [descripcion, setDescripcion] = useState('')
  const [cliente, setCliente] = useState('')
  const [proyecto, setProyecto] = useState('')
  const [rol, setRol] = useState('')
  const [experiencia, setExperiencia] = useState<number | ''>('')
  const [tecnologias, setTecnologias] = useState<string[]>([])
  const [idiomas, setIdiomas] = useState<string[]>([])
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

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

  const guardarBorrador = async () => {
    setError('')
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
          className="bm-textarea"
          maxLength={1000}
          value={descripcion}
          onChange={(e) => setDescripcion(e.target.value)}
          placeholder="Ej. Necesito un desarrollador Backend Java Senior con mínimo 5 años de experiencia, conocimientos en Spring Boot y AWS, experiencia en el sector bancario e inglés B2."
        />
        <div className="bm-count">{descripcion.length}/1000</div>
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
            onChange={(e) => setCliente(e.target.value)}
          />
        </div>

        <div className="bm-field">
          <label htmlFor="proyecto">Proyecto</label>
          <input
            id="proyecto"
            placeholder="Nombre del proyecto"
            value={proyecto}
            onChange={(e) => setProyecto(e.target.value)}
          />
        </div>

        <div className="bm-field">
          <label htmlFor="rol">Rol requerido</label>
          <select id="rol" value={rol} onChange={(e) => setRol(e.target.value)}>
            <option value="">Seleccionar rol</option>
            {ROLES.map((r) => (
              <option key={r}>{r}</option>
            ))}
          </select>
        </div>

        <div className="bm-field">
          <label htmlFor="experiencia">Experiencia mínima</label>
          <select
            id="experiencia"
            value={experiencia}
            onChange={(e) => setExperiencia(e.target.value === '' ? '' : Number(e.target.value))}
          >
            <option value="">Seleccionar exp</option>
            {EXPERIENCIAS.map((n) => (
              <option key={n} value={n}>
                {n}+ años
              </option>
            ))}
          </select>
        </div>

        <CampoChips
          id="tecnologias"
          etiqueta="Tecnologías y habilidades"
          placeholder="Buscar tecnología…"
          valores={tecnologias}
          onCambio={setTecnologias}
        />

        <CampoChips
          id="idiomas"
          etiqueta="Idiomas"
          placeholder="Agregar idioma…"
          valores={idiomas}
          onCambio={setIdiomas}
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
        <button className="bm-btn bm-btn-ghost" onClick={guardarBorrador}>
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

function CampoChips({
  id,
  etiqueta,
  placeholder,
  valores,
  onCambio,
}: {
  id: string
  etiqueta: string
  placeholder: string
  valores: string[]
  onCambio: (valores: string[]) => void
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
    <>
      <div className="bm-field">
        <label htmlFor={id}>{etiqueta}</label>
        <input id={id} placeholder={placeholder} onKeyDown={agregar} />
      </div>
      <div className="bm-chips">
        {valores.map((valor) => (
          <span className="bm-chip" key={valor}>
            {valor}
            <button onClick={() => onCambio(valores.filter((v) => v !== valor))} aria-label={`Quitar ${valor}`}>
              ×
            </button>
          </span>
        ))}
      </div>
    </>
  )
}
