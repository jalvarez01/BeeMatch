import { useEffect, useState } from 'react'

import { listarRoles } from '../api/candidatos'
import {
  DESCRIPCION_MAX,
  experienciaValida,
  idDeCampo,
  MENSAJE_EXPERIENCIA,
  type CampoValidado,
  type ErroresSolicitud,
  type ValoresSolicitud,
} from '../lib/solicitudForm'
import CampoCliente from './CampoCliente'
import { IconSpark } from './Icons'

interface Props {
  valores: ValoresSolicitud
  onCambio: (valores: ValoresSolicitud) => void
  errores: ErroresSolicitud
  onErrores: (errores: ErroresSolicitud) => void
  deshabilitado?: boolean
  /** Distingue los ids de los controles si hay dos formularios en la misma pantalla. */
  prefijo?: string
}

/**
 * Formulario de la solicitud: descripción, cliente, proyecto, rol, experiencia,
 * tecnologías e idiomas. Lo usan la pantalla de nueva búsqueda y el panel
 * "Ajustar criterios" de los resultados (HU-08 a HU-12, HU-15).
 */
export default function FormularioSolicitud({
  valores,
  onCambio,
  errores,
  onErrores,
  deshabilitado,
  prefijo = '',
}: Props) {
  const [roles, setRoles] = useState<string[]>([])

  // Los roles salen de lo que la IA identificó en las hojas de vida: al
  // cargar perfiles de un área nueva, aparecen aquí sin tocar código.
  useEffect(() => {
    listarRoles()
      .then((disponibles) => setRoles(disponibles.map((r) => r.nombre)))
      .catch(() => setRoles([]))
  }, [])

  const cambiar = (parcial: Partial<ValoresSolicitud>) => onCambio({ ...valores, ...parcial })
  const marcarError = (campo: CampoValidado, mensaje?: string) =>
    onErrores({ ...errores, [campo]: mensaje })

  const atributosDeError = (campo: CampoValidado) =>
    errores[campo]
      ? { 'aria-invalid': true, 'aria-describedby': `${idDeCampo(prefijo, campo)}-error` }
      : {}

  const id = (campo: CampoValidado | 'proyecto') => idDeCampo(prefijo, campo)
  const idRoles = `${prefijo}roles-sugeridos`

  return (
    <>
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
          id={id('descripcion')}
          className="bm-textarea"
          maxLength={DESCRIPCION_MAX}
          value={valores.descripcion}
          disabled={deshabilitado}
          onChange={(e) => {
            cambiar({ descripcion: e.target.value })
            if (errores.descripcion) marcarError('descripcion')
          }}
          aria-required="true"
          data-error={errores.descripcion ? 'true' : undefined}
          {...atributosDeError('descripcion')}
          placeholder="Ej. Necesito un desarrollador Backend Java Senior con mínimo 5 años de experiencia, conocimientos en Spring Boot y AWS, experiencia en el sector bancario e inglés B2."
        />
        <MensajeError id={`${id('descripcion')}-error`} mensaje={errores.descripcion} />
        <div className="bm-count">
          {valores.descripcion.length}/{DESCRIPCION_MAX}
        </div>
      </div>

      <h2 className="bm-h2">Detalles de la solicitud</h2>
      <p style={{ fontSize: 12, color: 'var(--muted)', margin: '0 0 14px' }}>
        Agrega contexto para mejorar la precisión de las recomendaciones.
      </p>

      <div className="bm-grid2">
        <div>
          <div className="bm-field" data-error={errores.cliente ? 'true' : undefined}>
            <label htmlFor={id('cliente')}>Cliente</label>
            <CampoCliente
              id={id('cliente')}
              valor={valores.cliente}
              deshabilitado={deshabilitado}
              onCambio={(cliente) => {
                cambiar({ cliente })
                if (errores.cliente) marcarError('cliente')
              }}
              atributosError={atributosDeError('cliente')}
            />
          </div>
          <MensajeError id={`${id('cliente')}-error`} mensaje={errores.cliente} />
        </div>

        <div className="bm-field">
          <label htmlFor={id('proyecto')}>Proyecto</label>
          <input
            id={id('proyecto')}
            placeholder="Nombre del proyecto"
            value={valores.proyecto}
            disabled={deshabilitado}
            onChange={(e) => cambiar({ proyecto: e.target.value })}
          />
        </div>

        <div>
          <div className="bm-field" data-error={errores.rol ? 'true' : undefined}>
            <label htmlFor={id('rol')}>Rol requerido</label>
            {/*
              Texto libre, no una lista cerrada: el rol no filtra en SQL, se suma
              a la consulta que resuelven los embeddings y el re-ranking, así que
              acepta cualquier cargo. La lista solo sugiere los que la IA ya
              identificó en las hojas de vida del repositorio.
            */}
            <input
              id={id('rol')}
              list={idRoles}
              placeholder="Escribir o elegir rol"
              value={valores.rol}
              disabled={deshabilitado}
              onChange={(e) => {
                cambiar({ rol: e.target.value })
                if (errores.rol) marcarError('rol')
              }}
              aria-required="true"
              {...atributosDeError('rol')}
            />
            <datalist id={idRoles}>
              {roles.map((r) => (
                <option key={r} value={r} />
              ))}
            </datalist>
          </div>
          <MensajeError id={`${id('rol')}-error`} mensaje={errores.rol} />
        </div>

        <div>
          <div className="bm-field" data-error={errores.experiencia ? 'true' : undefined}>
            <label htmlFor={id('experiencia')}>Experiencia mínima</label>
            {/*
              HU-10: solo enteros positivos. Lo que no es dígito no entra al
              campo y el aviso explica por qué, en vez de ignorar la tecla.
            */}
            <input
              id={id('experiencia')}
              inputMode="numeric"
              maxLength={2}
              placeholder="Años, ej. 5"
              value={valores.experiencia}
              disabled={deshabilitado}
              onChange={(e) => {
                const digitos = e.target.value.replace(/\D/g, '')
                const experiencia = digitos === '' ? '' : Number(digitos)
                cambiar({ experiencia })
                const valido = digitos === e.target.value && experienciaValida(experiencia)
                marcarError('experiencia', valido ? undefined : MENSAJE_EXPERIENCIA)
              }}
              {...atributosDeError('experiencia')}
            />
          </div>
          <MensajeError id={`${id('experiencia')}-error`} mensaje={errores.experiencia} />
        </div>

        <CampoChips
          id={`${prefijo}tecnologias`}
          etiqueta="Tecnologías y habilidades"
          placeholder="Buscar tecnología…"
          valores={valores.tecnologias}
          onCambio={(tecnologias) => cambiar({ tecnologias })}
          deshabilitado={deshabilitado}
        />

        <CampoChips
          id={`${prefijo}idiomas`}
          etiqueta="Idiomas"
          placeholder="Agregar idioma…"
          valores={valores.idiomas}
          onCambio={(idiomas) => cambiar({ idiomas })}
          deshabilitado={deshabilitado}
        />
      </div>
    </>
  )
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
