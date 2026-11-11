/**
 * Lógica del formulario de solicitud, sin React: valores iniciales, validación y el
 * cuerpo que se envía al servidor. La comparten la pantalla de nueva búsqueda y el
 * panel "Ajustar criterios" de los resultados (HU-09, HU-10, HU-12, HU-15).
 */

import type {
  AjustePayload,
  Criterio,
  ParametrosBusqueda,
  Solicitud,
  SolicitudPayload,
} from '../types'
// Con extensión: `npm test` corre este módulo directamente con Node, sin compilar.
import { GRUPOS_CRITERIO, valoresDelGrupo, type GrupoCriterio } from './criterios.ts'

export const DESCRIPCION_MIN = 15
export const DESCRIPCION_MAX = 1000
export const EXPERIENCIA_MAX = 50

export const MENSAJE_DESCRIPCION_CORTA = `La descripción es muy corta. Describe el perfil con más detalle (mínimo ${DESCRIPCION_MIN} caracteres).`
export const MENSAJE_DESCRIPCION_VACIA =
  'Falta la descripción del perfil. Cuéntale a BeeMatch qué perfil necesitas.'
export const MENSAJE_CLIENTE_VACIO = 'Indica el cliente que originó la solicitud.'
export const MENSAJE_ROL_VACIO = 'Falta el rol requerido. Escríbelo o elige uno de la lista.'
export const MENSAJE_EXPERIENCIA = `Ingresa solo números enteros positivos (de 1 a ${EXPERIENCIA_MAX} años).`

/** Campos que se validan, en el orden del formulario. */
export type CampoValidado = 'descripcion' | 'cliente' | 'rol' | 'experiencia'
export type ErroresSolicitud = Partial<Record<CampoValidado, string>>
export const ORDEN_CAMPOS: CampoValidado[] = ['descripcion', 'cliente', 'rol', 'experiencia']

/** Lo que el formulario edita. */
export interface ValoresSolicitud {
  descripcion: string
  cliente: string
  proyecto: string
  rol: string
  experiencia: number | ''
  // HU-09: un campo por grupo de criterios, cada uno con varios valores.
  tecnologias: string[]
  frameworks: string[]
  otros: string[]
  idiomas: string[]
  /**
   * Criterios con los que se abrió el formulario. El formulario solo edita el texto de
   * cada grupo; esta copia permite conservar el tipo, el peso y lo obligatorio de los
   * que no se tocaron, en lugar de aplanarlos.
   */
  criteriosOriginales: Criterio[]
}

/** Forma común de una solicitud y de los parámetros de una ejecución. */
interface OrigenCriterios {
  descripcion_libre: string
  rol_buscado: string | null
  experiencia_min: number | null
  cliente: string | null
  proyecto: string | null
  criterios: Criterio[]
}

export function valoresVacios(): ValoresSolicitud {
  return {
    descripcion: '',
    cliente: '',
    proyecto: '',
    rol: '',
    experiencia: '',
    tecnologias: [],
    frameworks: [],
    otros: [],
    idiomas: [],
    criteriosOriginales: [],
  }
}

export function origenDeSolicitud(solicitud: Solicitud): OrigenCriterios {
  return {
    descripcion_libre: solicitud.descripcion_libre,
    rol_buscado: solicitud.rol_buscado,
    experiencia_min: solicitud.experiencia_min,
    cliente: solicitud.cliente_nombre,
    proyecto: solicitud.proyecto_nombre,
    criterios: solicitud.criterios,
  }
}

/** Valores iniciales del formulario a partir de una solicitud o de los parámetros de una ejecución. */
export function valoresDesde(origen: OrigenCriterios | ParametrosBusqueda): ValoresSolicitud {
  return {
    descripcion: origen.descripcion_libre,
    cliente: origen.cliente ?? '',
    proyecto: origen.proyecto ?? '',
    rol: origen.rol_buscado ?? '',
    experiencia: origen.experiencia_min ?? '',
    // HU-09: cada criterio vuelve al campo de su tipo (un framework no se mezcla con las tecnologías).
    tecnologias: valoresDelGrupo(origen.criterios, 'tecnologias'),
    frameworks: valoresDelGrupo(origen.criterios, 'frameworks'),
    otros: valoresDelGrupo(origen.criterios, 'otros'),
    idiomas: valoresDelGrupo(origen.criterios, 'idiomas'),
    criteriosOriginales: origen.criterios,
  }
}

/**
 * Un criterio que ya existía en el mismo campo conserva su tipo, peso y obligatoriedad;
 * uno nuevo toma el tipo principal del campo donde se escribió.
 */
function criterioDe(valores: ValoresSolicitud, valor: string, grupo: GrupoCriterio): Criterio {
  const previo = valores.criteriosOriginales.find(
    (c) => c.valor === valor && grupo.tipos.includes(c.tipo),
  )
  if (previo) return { tipo: previo.tipo, valor, obligatorio: previo.obligatorio, peso: previo.peso }
  return { tipo: grupo.tipos[0], valor, obligatorio: false, peso: 1 }
}

/**
 * Criterios de todos los campos. Los que ya existían mantienen su orden original y los
 * nuevos van al final: confirmar un ajuste sin cambios reenvía exactamente lo mismo (HU-15).
 */
function criteriosDe(valores: ValoresSolicitud): Criterio[] {
  const posicionOriginal = (criterio: Criterio) => {
    const indice = valores.criteriosOriginales.findIndex(
      (c) => c.valor === criterio.valor && c.tipo === criterio.tipo,
    )
    return indice === -1 ? Number.POSITIVE_INFINITY : indice
  }
  return GRUPOS_CRITERIO.flatMap((grupo) =>
    valores[grupo.campo].map((valor) => criterioDe(valores, valor, grupo)),
  )
    .map((criterio, orden) => ({ criterio, orden, posicion: posicionOriginal(criterio) }))
    .sort((a, b) => a.posicion - b.posicion || a.orden - b.orden)
    .map(({ criterio }) => criterio)
}

/** Cuerpo para crear o actualizar una solicitud. */
export function construirPayload(valores: ValoresSolicitud): SolicitudPayload {
  return {
    descripcion_libre: valores.descripcion,
    rol_buscado: valores.rol.trim() || null,
    experiencia_min: valores.experiencia === '' ? null : valores.experiencia,
    cliente: valores.cliente.trim() || null,
    proyecto: valores.proyecto.trim() || null,
    criterios: criteriosDe(valores),
  }
}

/** Cuerpo del ajuste (HU-15): reemplaza la solicitud completa, así que no omite nada. */
export function construirAjuste(valores: ValoresSolicitud): AjustePayload {
  const payload = construirPayload(valores)
  return {
    descripcion_libre: payload.descripcion_libre,
    rol_buscado: payload.rol_buscado ?? null,
    experiencia_min: payload.experiencia_min ?? null,
    cliente: payload.cliente ?? null,
    proyecto: payload.proyecto ?? null,
    criterios: payload.criterios,
  }
}

/** HU-10: vacío es válido (no exige mínimo); si hay valor, entero entre 1 y el máximo. */
export function experienciaValida(experiencia: number | ''): boolean {
  return (
    experiencia === '' ||
    (Number.isInteger(experiencia) && experiencia > 0 && experiencia <= EXPERIENCIA_MAX)
  )
}

function descripcionMuyCorta(descripcion: string): boolean {
  const texto = descripcion.trim()
  return texto.length > 0 && texto.length < DESCRIPCION_MIN
}

/**
 * Errores de los campos. El cliente es obligatorio también en un borrador (HU-12);
 * rol y descripción solo para buscar, porque un borrador puede quedar incompleto (HU-10).
 */
export function validarSolicitud(valores: ValoresSolicitud, paraBuscar: boolean): ErroresSolicitud {
  const errores: ErroresSolicitud = {}
  if (paraBuscar) {
    if (!valores.descripcion.trim()) errores.descripcion = MENSAJE_DESCRIPCION_VACIA
    else if (descripcionMuyCorta(valores.descripcion)) errores.descripcion = MENSAJE_DESCRIPCION_CORTA
  }
  if (!valores.cliente.trim()) errores.cliente = MENSAJE_CLIENTE_VACIO
  if (paraBuscar && !valores.rol.trim()) errores.rol = MENSAJE_ROL_VACIO
  if (!experienciaValida(valores.experiencia)) errores.experiencia = MENSAJE_EXPERIENCIA
  return errores
}

/** El primer campo con error, en el orden del formulario, para llevarle el foco. */
export function primerCampoConError(errores: ErroresSolicitud): CampoValidado | undefined {
  return ORDEN_CAMPOS.find((campo) => errores[campo])
}

/** Mayúsculas, minúsculas y espacios de más no distinguen un cliente de otro (HU-12). */
export function normalizarNombre(nombre: string): string {
  return nombre.split(/\s+/).filter(Boolean).join(' ').toLocaleLowerCase('es')
}

/** ¿Los criterios de dos ejecuciones son los mismos? Sirve para avisar si el ajuste no cambió nada. */
export function mismosCriterios(a: ValoresSolicitud, b: ValoresSolicitud): boolean {
  const claveDe = (v: ValoresSolicitud) =>
    JSON.stringify([
      v.descripcion.trim(),
      normalizarNombre(v.cliente),
      normalizarNombre(v.proyecto),
      v.rol.trim(),
      v.experiencia,
      ...GRUPOS_CRITERIO.map((grupo) => [...v[grupo.campo]].sort()),
    ])
  return claveDe(a) === claveDe(b)
}

/** Id del control de cada campo; `prefijo` evita choques si hay dos formularios en la pantalla. */
export function idDeCampo(prefijo: string, campo: CampoValidado | 'proyecto'): string {
  return `${prefijo}${campo}`
}

/** Lleva el foco al control del campo (HU-10: el primer campo con error). */
export function enfocarCampo(prefijo: string, campo: CampoValidado): void {
  document.getElementById(idDeCampo(prefijo, campo))?.focus()
}
