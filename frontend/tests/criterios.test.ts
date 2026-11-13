// Pruebas de los campos estructurados de la solicitud (HU-09) y de cómo viajan por el
// ajuste de criterios (HU-15). Corren con el ejecutor de Node:  npm test
import assert from 'node:assert/strict'
import { test } from 'node:test'

import { agruparCriterios, GRUPOS_CRITERIO, grupoDeTipo } from '../src/lib/criterios.ts'
import {
  construirAjuste,
  construirPayload,
  mismosCriterios,
  valoresDesde,
  valoresVacios,
  type ValoresSolicitud,
} from '../src/lib/solicitudForm.ts'
import type { Criterio, ParametrosBusqueda } from '../src/types.ts'

function formulario(cambios: Partial<ValoresSolicitud> = {}): ValoresSolicitud {
  return {
    ...valoresVacios(),
    descripcion: 'Desarrollador Backend Java para el core bancario de un cliente.',
    cliente: 'Bancolombia',
    rol: 'Desarrollador Backend',
    experiencia: 5,
    ...cambios,
  }
}

const EJECUCION: ParametrosBusqueda = {
  descripcion_libre: 'Desarrollador Backend Java para el core bancario de un cliente.',
  rol_buscado: 'Desarrollador Backend',
  experiencia_min: 5,
  cliente_id: 'c1',
  cliente: 'Bancolombia',
  proyecto_id: null,
  proyecto: null,
  criterios: [
    { tipo: 'TECNOLOGIA', valor: 'Java', obligatorio: false, peso: 1 },
    { tipo: 'TECNOLOGIA', valor: 'AWS', obligatorio: false, peso: 1 },
    { tipo: 'FRAMEWORK', valor: 'Spring Boot', obligatorio: true, peso: 2 },
    { tipo: 'OTRO', valor: 'Sector bancario', obligatorio: false, peso: 1 },
    { tipo: 'IDIOMA', valor: 'Inglés B2', obligatorio: false, peso: 1 },
  ],
}

// --- Criterio 1: el formulario ofrece los campos ----------------------------------

test('HU-09 C1: hay un campo para tecnologías, frameworks, otros conocimientos e idiomas', () => {
  assert.deepEqual(
    GRUPOS_CRITERIO.map((g) => g.etiqueta),
    ['Tecnologías', 'Frameworks', 'Otros conocimientos', 'Idiomas'],
  )
})

test('HU-09 C1: cada campo guarda su propio tipo de criterio', () => {
  const payload = construirPayload(
    formulario({
      tecnologias: ['Java'],
      frameworks: ['Spring Boot'],
      otros: ['Sector bancario'],
      idiomas: ['Inglés B2'],
    }),
  )
  assert.deepEqual(
    payload.criterios.map((c) => [c.tipo, c.valor]),
    [
      ['TECNOLOGIA', 'Java'],
      ['FRAMEWORK', 'Spring Boot'],
      ['OTRO', 'Sector bancario'],
      ['IDIOMA', 'Inglés B2'],
    ],
  )
  assert.equal(payload.rol_buscado, 'Desarrollador Backend')
  assert.equal(payload.experiencia_min, 5)
})

// --- Criterio 2: tecnologías admite varios valores ----------------------------------

test('HU-09 C2: se registran varias tecnologías y cada una es un criterio', () => {
  const payload = construirPayload(formulario({ tecnologias: ['Java', 'Python', 'AWS'] }))
  assert.deepEqual(
    payload.criterios.map((c) => c.valor),
    ['Java', 'Python', 'AWS'],
  )
  assert.ok(payload.criterios.every((c) => c.tipo === 'TECNOLOGIA'))
})

// --- Criterio 4: los criterios se ven agrupados ------------------------------------

test('HU-09 C4: los criterios se agrupan en el orden del formulario', () => {
  const grupos = agruparCriterios(EJECUCION.criterios)
  assert.deepEqual(
    grupos.map((g) => [g.etiqueta, g.valores]),
    [
      ['Tecnologías', ['Java', 'AWS']],
      ['Frameworks', ['Spring Boot']],
      ['Otros conocimientos', ['Sector bancario']],
      ['Idiomas', ['Inglés B2']],
    ],
  )
})

test('HU-09 C4: sin criterios no hay grupos y no se repiten valores', () => {
  assert.deepEqual(agruparCriterios([]), [])
  const grupos = agruparCriterios([
    { tipo: 'TECNOLOGIA', valor: 'Java' },
    { tipo: 'TECNOLOGIA', valor: 'Java ' },
  ])
  assert.deepEqual(grupos[0].valores, ['Java'])
})

test('HU-09: dominio y certificación se muestran en "Otros conocimientos"', () => {
  assert.equal(grupoDeTipo('DOMINIO').etiqueta, 'Otros conocimientos')
  assert.equal(grupoDeTipo('CERTIFICACION').etiqueta, 'Otros conocimientos')
})

// --- HU-15: los campos de HU-09 viajan intactos por el ajuste ----------------------

test('HU-15: el ajuste abre cada criterio de la ejecución en su campo', () => {
  const valores = valoresDesde(EJECUCION)
  assert.deepEqual(valores.tecnologias, ['Java', 'AWS'])
  assert.deepEqual(valores.frameworks, ['Spring Boot'])
  assert.deepEqual(valores.otros, ['Sector bancario'])
  assert.deepEqual(valores.idiomas, ['Inglés B2'])
})

test('HU-15: confirmar el ajuste sin cambios reenvía exactamente los mismos criterios', () => {
  assert.deepEqual(construirAjuste(valoresDesde(EJECUCION)).criterios, EJECUCION.criterios)
})

test('HU-15: agregar un framework al ajuste lo envía como FRAMEWORK y conserva el resto', () => {
  const inicial = valoresDesde(EJECUCION)
  const criterios: Criterio[] = construirAjuste({
    ...inicial,
    frameworks: [...inicial.frameworks, 'Quarkus'],
  }).criterios
  assert.deepEqual(criterios.slice(0, 5), EJECUCION.criterios)
  assert.deepEqual(criterios[5], { tipo: 'FRAMEWORK', valor: 'Quarkus', obligatorio: false, peso: 1 })
})

test('HU-15: un criterio de dominio que no se tocó conserva su tipo al ajustar', () => {
  const origen = {
    ...EJECUCION,
    criterios: [{ tipo: 'DOMINIO' as const, valor: 'Banca', obligatorio: true, peso: 3 }],
  }
  const valores = valoresDesde(origen)
  assert.deepEqual(valores.otros, ['Banca'])
  assert.deepEqual(construirAjuste({ ...valores, otros: ['Banca', 'Scrum'] }).criterios, [
    { tipo: 'DOMINIO', valor: 'Banca', obligatorio: true, peso: 3 },
    { tipo: 'OTRO', valor: 'Scrum', obligatorio: false, peso: 1 },
  ])
})

test('HU-15: cambiar frameworks u otros conocimientos cuenta como un ajuste real', () => {
  const inicial = valoresDesde(EJECUCION)
  assert.equal(mismosCriterios(inicial, { ...inicial, frameworks: ['Spring Boot', 'Django'] }), false)
  assert.equal(mismosCriterios(inicial, { ...inicial, otros: [] }), false)
  assert.equal(mismosCriterios(inicial, { ...inicial, frameworks: ['Spring Boot'] }), true)
})
