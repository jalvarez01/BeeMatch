/**
 * Grupos de criterios estructurados de la solicitud (HU-09): tecnologías, frameworks,
 * otros conocimientos e idiomas. Es la única definición de qué tipo de criterio va en
 * qué campo; la usan el formulario, el panel "Ajustar criterios" (HU-15), el historial
 * y los resultados. Agregar un grupo nuevo es agregar una entrada aquí.
 */

import type { Criterio, TipoCriterio } from '../types'

/** Campos del formulario que admiten varios valores. */
export type CampoCriterio = 'tecnologias' | 'frameworks' | 'otros' | 'idiomas'

export interface GrupoCriterio {
  campo: CampoCriterio
  etiqueta: string
  /** Tipos que el campo muestra y edita. El primero es el que recibe un valor nuevo. */
  tipos: readonly TipoCriterio[]
}

export const GRUPOS_CRITERIO: readonly GrupoCriterio[] = [
  { campo: 'tecnologias', etiqueta: 'Tecnologías', tipos: ['TECNOLOGIA'] },
  { campo: 'frameworks', etiqueta: 'Frameworks', tipos: ['FRAMEWORK'] },
  // DOMINIO y CERTIFICACION no tienen campo propio: si una solicitud los trae, se
  // ven y se editan aquí, conservando su tipo.
  { campo: 'otros', etiqueta: 'Otros conocimientos', tipos: ['OTRO', 'DOMINIO', 'CERTIFICACION'] },
  { campo: 'idiomas', etiqueta: 'Idiomas', tipos: ['IDIOMA'] },
]

const GRUPO_POR_DEFECTO = GRUPOS_CRITERIO.find((g) => g.campo === 'otros') as GrupoCriterio

/** Grupo al que pertenece un tipo. Uno desconocido cae en "Otros conocimientos" para no perderse. */
export function grupoDeTipo(tipo: TipoCriterio): GrupoCriterio {
  return GRUPOS_CRITERIO.find((g) => g.tipos.includes(tipo)) ?? GRUPO_POR_DEFECTO
}

/** Valores de un grupo, en el orden en que se registraron. */
export function valoresDelGrupo(criterios: Criterio[], campo: CampoCriterio): string[] {
  return criterios.filter((c) => grupoDeTipo(c.tipo).campo === campo).map((c) => c.valor)
}

export interface CriteriosDeGrupo {
  campo: CampoCriterio
  etiqueta: string
  valores: string[]
}

/** Grupos con al menos un valor, en el orden del formulario y sin valores repetidos. */
export function agruparCriterios(criterios: Pick<Criterio, 'tipo' | 'valor'>[]): CriteriosDeGrupo[] {
  return GRUPOS_CRITERIO.map((grupo) => ({
    campo: grupo.campo,
    etiqueta: grupo.etiqueta,
    valores: [
      ...new Set(
        criterios
          .filter((c) => grupoDeTipo(c.tipo).campo === grupo.campo)
          .map((c) => c.valor.trim())
          .filter(Boolean),
      ),
    ],
  })).filter((grupo) => grupo.valores.length > 0)
}
