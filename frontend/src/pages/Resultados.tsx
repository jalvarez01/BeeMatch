import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import {
  ejecutarBusqueda,
  esperaCancelada,
  esperarResultado,
  etapaPorDefecto,
  listarEjecuciones,
  marcarPreseleccion,
  obtenerResultados,
  reejecutarBusqueda,
} from '../api/busquedas'
import { exportarPreseleccion } from '../api/preseleccion'
import { obtenerSolicitud } from '../api/solicitudes'
import { AfinidadBadge, AfinidadPorcentaje, LeyendaAfinidad, Tag } from '../components/Badges'
import BarraProgreso from '../components/BarraProgreso'
import EstadoVacio from '../components/EstadoVacio'
import FormularioSolicitud from '../components/FormularioSolicitud'
import { IconSpark } from '../components/Icons'
import ListaEjecuciones from '../components/ListaEjecuciones'
import { crearGuardaEnvio } from '../lib/envioUnico'
import { formatearFechaHora } from '../lib/formato'
import {
  construirAjuste,
  enfocarCampo,
  origenDeSolicitud,
  primerCampoConError,
  validarSolicitud,
  valoresDesde,
  valoresVacios,
  type ErroresSolicitud,
  type ValoresSolicitud,
} from '../lib/solicitudForm'
import type { BusquedaResultado, EjecucionResumen, Solicitud } from '../types'

const MENSAJE_SIN_CANDIDATOS = 'No se encontraron candidatos afines al perfil solicitado'
// HU-25: el mismo texto que responde el backend (export_service.MENSAJE_SIN_PRESELECCION).
const MENSAJE_SIN_PRESELECCION = 'Debes seleccionar al menos un candidato para exportar.'

const PREFIJO_AJUSTE = 'ajuste-'

/** HU-12, HU-15, HU-17, HU-18, HU-20, HU-22, HU-23, HU-24, HU-25. */
export default function Resultados() {
  const { busquedaId = '' } = useParams()
  const navegar = useNavigate()

  const [resultado, setResultado] = useState<BusquedaResultado | null>(null)
  const [solicitud, setSolicitud] = useState<Solicitud | null>(null)
  const [etapa, setEtapa] = useState('Preparando la consulta')
  const [progreso, setProgreso] = useState(0)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [solicitudIdReintento, setSolicitudIdReintento] = useState('')
  const [avisoPreseleccion, setAvisoPreseleccion] = useState('')
  const [avisoExportacion, setAvisoExportacion] = useState('')
  const [exportando, setExportando] = useState<'PDF' | 'XLSX' | null>(null)

  // HU-15: ejecuciones de la solicitud y panel para ajustar los criterios.
  const [ejecuciones, setEjecuciones] = useState<EjecucionResumen[]>([])
  const [ajustando, setAjustando] = useState(false)
  const [valoresAjuste, setValoresAjuste] = useState<ValoresSolicitud>(valoresVacios)
  const [erroresAjuste, setErroresAjuste] = useState<ErroresSolicitud>({})
  const [errorAjuste, setErrorAjuste] = useState('')
  const [enviandoAjuste, setEnviandoAjuste] = useState(false)
  // Bloquea el segundo clic de inmediato, sin esperar a que el botón se pinte deshabilitado.
  const guardaAjuste = useRef(crearGuardaEnvio())

  // HU-22: al salir de la pantalla, o al volver a intentar, se deja de sondear el
  // análisis anterior en vez de dejarlo corriendo en segundo plano.
  const control = useRef<AbortController | null>(null)

  const cargar = useCallback(async () => {
    control.current?.abort()
    const actual = new AbortController()
    control.current = actual

    setCargando(true)
    setError('')
    setEtapa('Preparando la consulta')
    setProgreso(0)
    // HU-15: al pasar a otra ejecución no se deja a la vista la anterior mientras la nueva se procesa.
    setResultado(null)
    setSolicitud(null)
    setAjustando(false)
    setErrorAjuste('')
    try {
      const inicial = await obtenerResultados(busquedaId)
      setSolicitudIdReintento(inicial.solicitud_id)
      // Sin la lista de ejecuciones la pantalla funciona igual: solo falta el selector.
      listarEjecuciones(inicial.solicitud_id)
        .then((lista) => {
          if (!actual.signal.aborted) setEjecuciones(lista)
        })
        .catch(() => setEjecuciones([]))

      const final =
        inicial.estado === 'COMPLETADA'
          ? inicial
          : await esperarResultado(
              busquedaId,
              (estado) => {
                setEtapa(estado.etapa ?? etapaPorDefecto(estado.estado))
                setProgreso(estado.progreso)
              },
              { signal: actual.signal },
            )

      const solicitudDeLaBusqueda = await obtenerSolicitud(final.solicitud_id)
      if (actual.signal.aborted) return
      setResultado(final)
      setSolicitud(solicitudDeLaBusqueda)
    } catch (e) {
      if (esperaCancelada(e) || actual.signal.aborted) return
      setError((e as Error).message)
    } finally {
      if (!actual.signal.aborted) setCargando(false)
    }
  }, [busquedaId])

  useEffect(() => {
    void cargar()
    return () => control.current?.abort()
  }, [cargar])

  const reintentar = async () => {
    if (!solicitudIdReintento) {
      await cargar()
      return
    }

    setCargando(true)
    setError('')

    try {
      const nuevaBusqueda = await ejecutarBusqueda(solicitudIdReintento)
      navegar(`/resultados/${nuevaBusqueda.id}`)
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setCargando(false)
    }
  }

  // HU-24: la casilla cambia al instante. Si el servidor no guarda el cambio,
  // vuelve a su estado anterior y se avisa sin perder la pantalla de resultados.
  const alternarPreseleccion = async (recomendacionId: string, valor: boolean) => {
    const fijar = (preseleccionado: boolean) =>
      setResultado((previo) =>
        previo
          ? {
              ...previo,
              recomendaciones: previo.recomendaciones.map((r) =>
                r.id === recomendacionId ? { ...r, preseleccionado } : r,
              ),
            }
          : previo,
      )

    setAvisoPreseleccion('')
    setAvisoExportacion('')
    fijar(valor)
    try {
      const actualizada = await marcarPreseleccion(recomendacionId, valor)
      fijar(actualizada.preseleccionado)
    } catch (e) {
      fijar(!valor)
      setAvisoPreseleccion(`No se pudo guardar la preselección. ${(e as Error).message}`)
    }
  }

  // HU-25: los errores de la exportación se avisan sin cambiar la pantalla de resultados.
  const exportar = async (formato: 'PDF' | 'XLSX') => {
    setAvisoExportacion('')
    if (!resultado?.recomendaciones.some((r) => r.preseleccionado)) {
      setAvisoExportacion(MENSAJE_SIN_PRESELECCION)
      return
    }
    setExportando(formato)
    try {
      await exportarPreseleccion(busquedaId, formato)
    } catch (e) {
      setAvisoExportacion((e as Error).message)
    } finally {
      setExportando(null)
    }
  }

  /** HU-15: abre el panel con los criterios de ESTA ejecución como valores iniciales. */
  const abrirAjuste = () => {
    if (!resultado) return
    const origen = resultado.parametros ?? (solicitud ? origenDeSolicitud(solicitud) : null)
    setValoresAjuste(origen ? valoresDesde(origen) : valoresVacios())
    setErroresAjuste({})
    setErrorAjuste('')
    setAjustando(true)
  }

  const confirmarAjuste = () =>
    guardaAjuste.current.ejecutar(async () => {
      if (!resultado) return
      setErrorAjuste('')
      const encontrados = validarSolicitud(valoresAjuste, true)
      setErroresAjuste(encontrados)
      const primero = primerCampoConError(encontrados)
      if (primero) {
        enfocarCampo(PREFIJO_AJUSTE, primero)
        return
      }
      setEnviandoAjuste(true)
      try {
        const nueva = await reejecutarBusqueda(resultado.solicitud_id, construirAjuste(valoresAjuste))
        navegar(`/resultados/${nueva.id}`)
      } catch (e) {
        setErrorAjuste((e as Error).message)
      } finally {
        setEnviandoAjuste(false)
      }
    })

  if (cargando && !resultado) {
    return <BarraProgreso etapa={etapa} progreso={progreso} />
  }

  if (error) {
    // HU-26: el error se explica y la solicitud no se pierde.
    return (
      <>
        <div className="bm-alert bm-alert-error">{error}</div>
        <button
          className="bm-btn bm-btn-ghost"
          onClick={() => void reintentar()}
          disabled={cargando}
        >
          {cargando ? 'Reintentando...' : 'Reintentar'}
        </button>
        {/* HU-15: si un ajuste falla, las ejecuciones anteriores siguen disponibles. */}
        <div style={{ marginTop: 18 }}>
          <ListaEjecuciones
            ejecuciones={ejecuciones}
            actualId={busquedaId}
            onAbrir={(id) => navegar(`/resultados/${id}`)}
          />
        </div>
      </>
    )
  }

  if (!resultado) return null

  const preseleccionados = resultado.recomendaciones.filter((r) => r.preseleccionado).length
  // HU-15: lo que se pidió en ESTA ejecución. Las anteriores a HU-15 no lo guardaron: se usa la solicitud.
  const parametros = resultado.parametros
  const rolBuscado = parametros ? parametros.rol_buscado : (solicitud?.rol_buscado ?? null)
  const clienteNombre = parametros ? parametros.cliente : (solicitud?.cliente_nombre ?? null)
  const proyectoNombre = parametros ? parametros.proyecto : (solicitud?.proyecto_nombre ?? null)
  const experienciaMin = parametros ? parametros.experiencia_min : (solicitud?.experiencia_min ?? null)
  const criterios = (parametros?.criterios ?? solicitud?.criterios ?? []).map((c) => c.valor)
  const esAnterior = ejecuciones.some((e) => e.id === resultado.id && !e.es_mas_reciente)
  const masReciente = ejecuciones.find((e) => e.es_mas_reciente)

  return (
    <>
      <button className="bm-btn-back" onClick={() => navegar('/historial')}>
        ← Resultados de búsqueda
      </button>

      <div className="bm-row-between" style={{ marginBottom: 16 }}>
        <div>
          <h2 className="bm-h2">{rolBuscado ?? 'Perfil solicitado'}</h2>
          <p style={{ fontSize: 12, color: 'var(--muted)', margin: '0 0 6px' }}>
            {[clienteNombre ?? 'Sin cliente', proyectoNombre].filter(Boolean).join(' · ')}
          </p>
          <p style={{ fontSize: 11, color: 'var(--muted-2)', margin: 0 }}>
            {[...criterios, experienciaMin ? `${experienciaMin}+ años` : ''].filter(Boolean).join(' · ')}
          </p>
          {resultado.total_ejecuciones > 1 && (
            <p style={{ fontSize: 11, color: 'var(--muted-2)', margin: '4px 0 0' }}>
              Ejecución {resultado.numero_ejecucion} de {resultado.total_ejecuciones}
              {resultado.created_at && ` · ${formatearFechaHora(resultado.created_at)}`}
            </p>
          )}
        </div>
        {!ajustando && (
          <button className="bm-btn bm-btn-ghost" onClick={abrirAjuste}>
            Ajustar criterios
          </button>
        )}
      </div>

      {esAnterior && (
        <div className="bm-banner-anterior" role="status">
          <span>
            Estás viendo una ejecución anterior ({resultado.numero_ejecucion} de{' '}
            {resultado.total_ejecuciones}). Los resultados más recientes son otros.
          </span>
          {masReciente && (
            <button
              className="bm-btn bm-btn-ghost"
              onClick={() => navegar(`/resultados/${masReciente.id}`)}
            >
              Ver la más reciente →
            </button>
          )}
        </div>
      )}

      {ajustando && (
        // HU-15: criterios de esta ejecución, editables, con cliente y proyecto. Al confirmar se
        // ejecuta de nuevo y la ejecución actual queda guardada con sus propios criterios.
        <section className="bm-card" aria-label="Ajustar criterios" style={{ marginBottom: 22 }}>
          <h2 className="bm-h2" style={{ marginTop: 0 }}>
            Ajustar criterios
          </h2>
          <p style={{ fontSize: 12, color: 'var(--muted)', margin: '0 0 14px' }}>
            Estos son los criterios de la ejecución que estás viendo. Edítalos y vuelve a buscar:
            esta ejecución y sus resultados se conservan en el historial.
          </p>
          {errorAjuste && (
            <div className="bm-alert bm-alert-error" role="alert">
              {errorAjuste}
            </div>
          )}
          <FormularioSolicitud
            valores={valoresAjuste}
            onCambio={setValoresAjuste}
            errores={erroresAjuste}
            onErrores={setErroresAjuste}
            deshabilitado={enviandoAjuste}
            prefijo={PREFIJO_AJUSTE}
          />
          <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 10, marginTop: 18 }}>
            <button
              className="bm-btn bm-btn-soft"
              onClick={() => setAjustando(false)}
              disabled={enviandoAjuste}
            >
              Cancelar
            </button>
            <button
              className="bm-btn bm-btn-primary"
              onClick={() => void confirmarAjuste()}
              disabled={enviandoAjuste}
              aria-busy={enviandoAjuste}
            >
              {enviandoAjuste ? 'Analizando…' : 'Confirmar y volver a buscar'}
            </button>
          </div>
        </section>
      )}

      <ListaEjecuciones
        ejecuciones={ejecuciones}
        actualId={resultado.id}
        onAbrir={(id) => navegar(`/resultados/${id}`)}
      />

      <div
        className="bm-tip"
        style={{ display: 'flex', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap', marginBottom: 22 }}
      >
        <span style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: 12, fontWeight: 600 }}>
          <IconSpark /> Análisis completado
        </span>
        <span style={{ fontSize: 12, color: 'var(--muted)' }}>
          {resultado.cv_analizados} hojas de vida analizadas ·{' '}
          {resultado.recomendaciones.length} candidatos superaron el nivel mínimo de afinidad
          {resultado.cv_no_procesables > 0 &&
            ` · ${resultado.cv_no_procesables} documentos no pudieron procesarse`}
        </span>
      </div>

      {resultado.recomendaciones.length > 0 && (
        <div className="bm-row-between" style={{ marginBottom: 14 }}>
          <div>
            <h2 className="bm-h2" style={{ margin: 0 }}>
              Candidatos recomendados
            </h2>
            <p style={{ fontSize: 12, color: 'var(--muted)', margin: 0 }}>
              Ordenados de mayor a menor afinidad con los criterios de la solicitud.
            </p>
            <LeyendaAfinidad />
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <span style={{ fontSize: 12, color: 'var(--muted)', whiteSpace: 'nowrap' }}>
              {preseleccionados === 1
                ? '1 candidato preseleccionado'
                : `${preseleccionados} candidatos preseleccionados`}
            </span>
            <button
              className="bm-btn bm-btn-dark"
              style={{ whiteSpace: 'nowrap' }}
              onClick={() => void exportar('PDF')}
              disabled={exportando !== null}
            >
              {exportando === 'PDF' ? 'Generando…' : 'Exportar PDF'}
            </button>
            <button
              className="bm-btn bm-btn-ghost"
              style={{ whiteSpace: 'nowrap' }}
              onClick={() => void exportar('XLSX')}
              disabled={exportando !== null}
            >
              {exportando === 'XLSX' ? 'Generando…' : 'Exportar Excel'}
            </button>
          </div>
        </div>
      )}

      {avisoPreseleccion && <div className="bm-alert bm-alert-error">{avisoPreseleccion}</div>}
      {avisoExportacion && (
        <div className="bm-alert bm-alert-error" role="alert">
          {avisoExportacion}
        </div>
      )}

      {resultado.recomendaciones.length === 0 && (
        // HU-23: el mensaje es explícito y sugiere flexibilizar la búsqueda.
        <EstadoVacio
          titulo={MENSAJE_SIN_CANDIDATOS}
          texto={
            `Se analizaron ${resultado.cv_analizados} hojas de vida y ninguna alcanzó el nivel ` +
            'mínimo de afinidad. Te sugerimos ajustar o flexibilizar los criterios de búsqueda: ' +
            'marca menos requisitos como obligatorios, amplía las tecnologías aceptadas o baja ' +
            'la experiencia mínima.'
          }
          accion={
            <button className="bm-btn bm-btn-primary" onClick={abrirAjuste}>
              Ajustar criterios de búsqueda
            </button>
          }
        />
      )}

      {resultado.recomendaciones.map((candidato) => (
        <article className="bm-cand" key={candidato.id}>
          <div className="score">
            <AfinidadPorcentaje
              className="p"
              puntaje={candidato.puntaje_afinidad}
              nivel={candidato.nivel}
            />
            <AfinidadBadge nivel={candidato.nivel} />
          </div>

          <div>
            <div className="name">{candidato.nombre}</div>
            <div className="meta">
              {candidato.rol_principal ?? 'Rol no especificado en la hoja de vida'}
              {candidato.anios_experiencia !== null &&
                ` · ${candidato.anios_experiencia} años de experiencia`}
            </div>
            <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
              {candidato.tecnologias.map((t) => (
                <Tag key={t}>{t}</Tag>
              ))}
            </div>
            {candidato.resumen_ia && <div className="note">✦ {candidato.resumen_ia}</div>}
          </div>

          <div className="actions">
            <label className="bm-check">
              <input
                type="checkbox"
                checked={candidato.preseleccionado}
                onChange={(e) => void alternarPreseleccion(candidato.id, e.target.checked)}
              />
              {candidato.preseleccionado ? 'Preseleccionado' : 'Preseleccionar'}
            </label>
            <button
              className="bm-btn bm-btn-ghost"
              onClick={() => navegar(`/candidato/${candidato.id}`)}
            >
              Ver detalle →
            </button>
          </div>
        </article>
      ))}
    </>
  )
}
