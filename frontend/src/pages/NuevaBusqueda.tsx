import { useEffect, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'

import { ejecutarBusqueda } from '../api/busquedas'
import { actualizarSolicitud, crearSolicitud, obtenerSolicitud } from '../api/solicitudes'
import FormularioSolicitud from '../components/FormularioSolicitud'
import { IconSpark } from '../components/Icons'
import { crearGuardaEnvio } from '../lib/envioUnico'
import {
  construirPayload,
  enfocarCampo,
  origenDeSolicitud,
  primerCampoConError,
  validarSolicitud,
  valoresDesde,
  valoresVacios,
  type ErroresSolicitud,
  type ValoresSolicitud,
} from '../lib/solicitudForm'

/** HU-08, HU-09, HU-10, HU-11, HU-12, HU-15. */
export default function NuevaBusqueda() {
  const navegar = useNavigate()
  const [params] = useSearchParams()
  const solicitudId = params.get('solicitud')

  const [valores, setValores] = useState<ValoresSolicitud>(valoresVacios)
  const [errores, setErrores] = useState<ErroresSolicitud>({})
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)
  // HU-22: bloquea el segundo clic de inmediato; el estado `enviando` tarda un render en llegar al botón.
  const guarda = useRef(crearGuardaEnvio())

  // HU-11 / HU-14 / HU-15: precarga de un borrador o de una solicitud duplicada.
  useEffect(() => {
    if (!solicitudId) return
    obtenerSolicitud(solicitudId)
      .then((solicitud) => setValores(valoresDesde(origenDeSolicitud(solicitud))))
      .catch((e: Error) => setError(e.message))
  }, [solicitudId])

  /**
   * HU-10 y HU-12: marca los campos con error y lleva el foco al primero. Un borrador
   * puede quedar incompleto, pero necesita cliente; una búsqueda necesita además rol y descripción.
   */
  const validar = (paraBuscar: boolean): boolean => {
    const encontrados = validarSolicitud(valores, paraBuscar)
    setErrores(encontrados)
    const primero = primerCampoConError(encontrados)
    if (!primero) return true
    enfocarCampo('', primero)
    return false
  }

  const guardarBorrador = () =>
    guarda.current.ejecutar(async () => {
      setError('')
      if (!validar(false)) return
      setEnviando(true)
      try {
        const solicitud = solicitudId
          ? await actualizarSolicitud(solicitudId, construirPayload(valores))
          : await crearSolicitud(construirPayload(valores))
        navegar(`/historial?guardada=${solicitud.id}`)
      } catch (e) {
        setError((e as Error).message)
      } finally {
        setEnviando(false)
      }
    })

  const buscar = () =>
    guarda.current.ejecutar(async () => {
      setError('')
      if (!validar(true)) return
      setEnviando(true)
      try {
        const solicitud = solicitudId
          ? await actualizarSolicitud(solicitudId, construirPayload(valores))
          : await crearSolicitud(construirPayload(valores))
        const busqueda = await ejecutarBusqueda(solicitud.id)
        navegar(`/resultados/${busqueda.id}`)
      } catch (e) {
        setError((e as Error).message)
      } finally {
        setEnviando(false)
      }
    })

  return (
    <>
      <h1 className="bm-h1">Nueva búsqueda con IA</h1>
      <p className="bm-sub">
        Describe el perfil que necesitas y BeeMatch encontrará los candidatos con mayor afinidad.
      </p>

      {error && <div className="bm-alert bm-alert-error">{error}</div>}

      <FormularioSolicitud
        valores={valores}
        onCambio={setValores}
        errores={errores}
        onErrores={setErrores}
        deshabilitado={enviando}
      />

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
        <button className="bm-btn bm-btn-soft" onClick={() => void guardarBorrador()} disabled={enviando}>
          Guardar borrador
        </button>
        <button className="bm-btn bm-btn-primary" onClick={() => void buscar()} disabled={enviando}>
          {enviando ? 'Analizando…' : 'Buscar candidatos con IA'}
        </button>
      </div>
    </>
  )
}
