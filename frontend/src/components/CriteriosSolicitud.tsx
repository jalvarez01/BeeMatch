import { agruparCriterios } from '../lib/criterios'
import type { Criterio } from '../types'

interface Props {
  criterios: Pick<Criterio, 'tipo' | 'valor'>[]
  experienciaMin?: number | null
}

/**
 * HU-09: criterios con los que se registró o ejecutó una solicitud, agrupados como en el
 * formulario (tecnologías, frameworks, otros conocimientos, idiomas) y con la experiencia
 * mínima. Lo usan el historial y la pantalla de resultados (HU-15), para que se vea qué
 * se pidió en cada campo.
 */
export default function CriteriosSolicitud({ criterios, experienciaMin }: Props) {
  const grupos = agruparCriterios(criterios)
  if (grupos.length === 0 && !experienciaMin) return null

  return (
    <dl className="bm-criterios" aria-label="Criterios de la solicitud">
      {experienciaMin ? (
        <div className="bm-criterios-grupo">
          <dt>Experiencia</dt>
          <dd>
            <span className="bm-tag">{experienciaMin}+ años</span>
          </dd>
        </div>
      ) : null}
      {grupos.map((grupo) => (
        <div className="bm-criterios-grupo" key={grupo.campo}>
          <dt>{grupo.etiqueta}</dt>
          <dd>
            {grupo.valores.map((valor) => (
              <span className="bm-tag" key={valor}>
                {valor}
              </span>
            ))}
          </dd>
        </div>
      ))}
    </dl>
  )
}
