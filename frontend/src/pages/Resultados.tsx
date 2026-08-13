import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { esperarResultado, marcarPreseleccion, obtenerResultados } from '../api/busquedas'
import { exportarPreseleccion } from '../api/preseleccion'
import { obtenerSolicitud } from '../api/solicitudes'
import { AfinidadBadge, Tag } from '../components/Badges'
import BarraProgreso from '../components/BarraProgreso'
import { IconSpark } from '../components/Icons'
import type { BusquedaResultado, Solicitud } from '../types'

/** HU-17, HU-18, HU-20, HU-22, HU-23, HU-24, HU-25. */
export default function Resultados() {
  const { busquedaId = '' } = useParams()
  const navegar = useNavigate()

  const [resultado, setResultado] = useState<BusquedaResultado | null>(null)
  const [solicitud, setSolicitud] = useState<Solicitud | null>(null)
  const [etapa, setEtapa] = useState('Preparando la consulta')
  const [progreso, setProgreso] = useState(0)
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')

  const cargar = useCallback(async () => {
    setCargando(true)
    setError('')
    try {
      const inicial = await obtenerResultados(busquedaId)

      const final =
        inicial.estado === 'COMPLETADA'
          ? inicial
          : await esperarResultado(busquedaId, (estado) => {
              setEtapa(estado.etapa ?? 'Analizando')
              setProgreso(estado.progreso)
            })

      setResultado(final)
      setSolicitud(await obtenerSolicitud(final.solicitud_id))
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setCargando(false)
    }
  }, [busquedaId])

  useEffect(() => {
    void cargar()
  }, [cargar])

  const alternarPreseleccion = async (recomendacionId: string, valor: boolean) => {
    const actualizada = await marcarPreseleccion(recomendacionId, valor)
    setResultado((previo) =>
      previo
        ? {
            ...previo,
            recomendaciones: previo.recomendaciones.map((r) =>
              r.id === recomendacionId ? { ...r, preseleccionado: actualizada.preseleccionado } : r,
            ),
          }
        : previo,
    )
  }

  const exportar = async () => {
    try {
      await exportarPreseleccion(busquedaId, 'XLSX')
    } catch (e) {
      setError((e as Error).message)
    }
  }

  if (cargando && !resultado) {
    return <BarraProgreso etapa={etapa} progreso={progreso} />
  }

  if (error) {
    // HU-26: el error se explica y la solicitud no se pierde.
    return (
      <>
        <div className="bm-alert bm-alert-error">{error}</div>
        <button className="bm-btn bm-btn-ghost" onClick={() => void cargar()}>
          Reintentar
        </button>
      </>
    )
  }

  if (!resultado) return null

  const criterios = solicitud?.criterios.map((c) => c.valor) ?? []

  return (
    <>
      <button className="bm-btn-back" onClick={() => navegar('/historial')}>
        ← Resultados de búsqueda
      </button>

      <div className="bm-row-between" style={{ marginBottom: 16 }}>
        <div>
          <h2 className="bm-h2">{solicitud?.rol_buscado ?? 'Perfil solicitado'}</h2>
          <p style={{ fontSize: 12, color: 'var(--muted)', margin: '0 0 6px' }}>
            {solicitud?.cliente_nombre} · {solicitud?.proyecto_nombre}
          </p>
          <p style={{ fontSize: 11, color: 'var(--muted-2)', margin: 0 }}>
            {[...criterios, solicitud?.experiencia_min ? `${solicitud.experiencia_min}+ años` : '']
              .filter(Boolean)
              .join(' · ')}
          </p>
        </div>
        <button
          className="bm-btn bm-btn-ghost"
          onClick={() => navegar(`/nueva-busqueda?solicitud=${resultado.solicitud_id}`)}
        >
          Ajustar criterios
        </button>
      </div>

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

      <div className="bm-row-between" style={{ marginBottom: 14 }}>
        <div>
          <h2 className="bm-h2" style={{ margin: 0 }}>
            Candidatos recomendados
          </h2>
          <p style={{ fontSize: 12, color: 'var(--muted)', margin: 0 }}>
            Ordenados de mayor a menor afinidad con los criterios de la solicitud.
          </p>
        </div>
        <button className="bm-btn bm-btn-dark" onClick={exportar}>
          Exportar preselección
        </button>
      </div>

      {resultado.recomendaciones.length === 0 && (
        <div className="bm-card">
          <div className="bm-empty">
            <h3>Ningún candidato superó el nivel mínimo de afinidad</h3>
            <p>
              Prueba ampliando los criterios o bajando la experiencia mínima. Se analizaron{' '}
              {resultado.cv_analizados} hojas de vida.
            </p>
          </div>
        </div>
      )}

      {resultado.recomendaciones.map((candidato) => (
        <article className="bm-cand" key={candidato.id}>
          <div className="score">
            <div className="p">{candidato.puntaje_afinidad}%</div>
            <AfinidadBadge nivel={candidato.nivel} />
          </div>

          <div>
            <div className="name">{candidato.nombre}</div>
            <div className="meta">
              {candidato.rol_principal} · {candidato.anios_experiencia} años de experiencia
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
