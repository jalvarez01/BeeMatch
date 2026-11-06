// Pruebas de la lógica del formulario de solicitud (HU-10, HU-12, HU-15).
// Corren con el ejecutor de Node, sin dependencias nuevas:  npm test
import assert from 'node:assert/strict'
import { test } from 'node:test'

import { crearGuardaEnvio } from '../src/lib/envioUnico.ts'
import { resumirParametros } from '../src/lib/formato.ts'
import {
  MENSAJE_CLIENTE_VACIO,
  MENSAJE_EXPERIENCIA,
  construirAjuste,
  construirPayload,
  mismosCriterios,
  normalizarNombre,
  primerCampoConError,
  validarSolicitud,
  valoresDesde,
  valoresVacios,
  type ValoresSolicitud,
} from '../src/lib/solicitudForm.ts'
import type { Criterio, ParametrosBusqueda } from '../src/types.ts'

const DESCRIPCION = 'Desarrollador Backend Java con Spring Boot y experiencia en banca.'

function completos(cambios: Partial<ValoresSolicitud> = {}): ValoresSolicitud {
  return {
    ...valoresVacios(),
    descripcion: DESCRIPCION,
    cliente: 'Bancolombia',
    rol: 'Desarrollador Backend',
    ...cambios,
  }
}

// --- HU-12: el cliente es obligatorio -----------------------------------------

test('sin cliente no se puede buscar y el mensaje es claro', () => {
  const errores = validarSolicitud(completos({ cliente: '' }), true)
  assert.equal(errores.cliente, MENSAJE_CLIENTE_VACIO)
})

test('un cliente de solo espacios cuenta como vacío', () => {
  assert.equal(validarSolicitud(completos({ cliente: '   ' }), true).cliente, MENSAJE_CLIENTE_VACIO)
})

test('tampoco se guarda un borrador sin cliente, aunque no pida rol ni descripción', () => {
  const errores = validarSolicitud(valoresVacios(), false)
  assert.deepEqual(Object.keys(errores), ['cliente'])
})

test('con cliente, rol y descripción no hay errores', () => {
  assert.deepEqual(validarSolicitud(completos(), true), {})
})

test('el foco va al primer campo con error en el orden del formulario', () => {
  assert.equal(primerCampoConError(validarSolicitud(valoresVacios(), true)), 'descripcion')
  assert.equal(
    primerCampoConError(validarSolicitud(completos({ cliente: '', rol: '' }), true)),
    'cliente',
  )
  assert.equal(primerCampoConError({}), undefined)
})

test('la experiencia mínima solo admite enteros de 1 a 50', () => {
  for (const valida of ['', 1, 50] as const) {
    assert.equal(validarSolicitud(completos({ experiencia: valida }), true).experiencia, undefined)
  }
  for (const invalida of [0, 51, 2.5]) {
    assert.equal(validarSolicitud(completos({ experiencia: invalida }), true).experiencia, MENSAJE_EXPERIENCIA)
  }
})

// --- HU-12: sin duplicar por mayúsculas ni espacios -----------------------------

test('los nombres de cliente se comparan sin mayúsculas ni espacios de más', () => {
  assert.equal(normalizarNombre('  ACME   S.A.S. '), 'acme s.a.s.')
  assert.equal(normalizarNombre('Acme\tS.A.S.'), normalizarNombre('acme s.a.s.'))
  assert.notEqual(normalizarNombre('Banco Uno'), normalizarNombre('Banco Dos'))
})

test('el payload lleva cliente y proyecto sin espacios en los extremos', () => {
  const payload = construirPayload(completos({ cliente: '  Bancolombia ', proyecto: ' Core Bancario ' }))
  assert.equal(payload.cliente, 'Bancolombia')
  assert.equal(payload.proyecto, 'Core Bancario')
})

test('un proyecto vacío se envía como nulo', () => {
  assert.equal(construirPayload(completos({ proyecto: '   ' })).proyecto, null)
})

// --- HU-15: valores iniciales y ajuste ------------------------------------------

const PARAMETROS: ParametrosBusqueda = {
  descripcion_libre: DESCRIPCION,
  rol_buscado: 'Desarrollador Backend',
  experiencia_min: 5,
  cliente_id: 'c1',
  cliente: 'Bancolombia',
  proyecto_id: 'p1',
  proyecto: 'Core Bancario',
  criterios: [
    { tipo: 'FRAMEWORK', valor: 'Spring Boot', obligatorio: true, peso: 2.5 },
    { tipo: 'TECNOLOGIA', valor: 'Java', obligatorio: false, peso: 1 },
    { tipo: 'IDIOMA', valor: 'Inglés B2', obligatorio: false, peso: 1 },
  ],
}

test('los criterios de la ejecución son los valores iniciales del ajuste, con cliente y proyecto', () => {
  const valores = valoresDesde(PARAMETROS)
  assert.equal(valores.descripcion, DESCRIPCION)
  assert.equal(valores.cliente, 'Bancolombia')
  assert.equal(valores.proyecto, 'Core Bancario')
  assert.equal(valores.rol, 'Desarrollador Backend')
  assert.equal(valores.experiencia, 5)
  assert.deepEqual(valores.tecnologias, ['Spring Boot', 'Java'])
  assert.deepEqual(valores.idiomas, ['Inglés B2'])
})

test('abrir el ajuste y confirmar sin tocar nada reenvía los mismos criterios', () => {
  const ajuste = construirAjuste(valoresDesde(PARAMETROS))
  assert.deepEqual(ajuste.criterios, PARAMETROS.criterios)
  assert.equal(ajuste.experiencia_min, 5)
  assert.equal(ajuste.cliente, 'Bancolombia')
  assert.equal(ajuste.proyecto, 'Core Bancario')
})

test('el ajuste conserva tipo, peso y obligatoriedad de lo que no se tocó y crea lo nuevo', () => {
  const valores = { ...valoresDesde(PARAMETROS), tecnologias: ['Spring Boot', 'Python'] }
  const criterios: Criterio[] = construirAjuste(valores).criterios
  assert.deepEqual(criterios[0], { tipo: 'FRAMEWORK', valor: 'Spring Boot', obligatorio: true, peso: 2.5 })
  assert.deepEqual(criterios[1], { tipo: 'TECNOLOGIA', valor: 'Python', obligatorio: false, peso: 1 })
  assert.deepEqual(criterios[2].tipo, 'IDIOMA')
})

test('lo que se quita del ajuste no se envía', () => {
  const valores = { ...valoresDesde(PARAMETROS), tecnologias: [], idiomas: [], experiencia: '' as const }
  const ajuste = construirAjuste(valores)
  assert.deepEqual(ajuste.criterios, [])
  assert.equal(ajuste.experiencia_min, null)
})

test('el ajuste siempre lleva todos los campos, también los vacíos', () => {
  const ajuste = construirAjuste(completos())
  assert.deepEqual(Object.keys(ajuste).sort(), [
    'cliente',
    'criterios',
    'descripcion_libre',
    'experiencia_min',
    'proyecto',
    'rol_buscado',
  ])
  assert.equal(ajuste.proyecto, null)
})

test('se detecta si el ajuste dejó los criterios como estaban', () => {
  const inicial = valoresDesde(PARAMETROS)
  assert.equal(mismosCriterios(inicial, { ...inicial, cliente: ' BANCOLOMIA '.replace('MIA', 'MBIA') }), true)
  assert.equal(mismosCriterios(inicial, { ...inicial, tecnologias: [...inicial.tecnologias, 'Go'] }), false)
  assert.equal(mismosCriterios(inicial, { ...inicial, experiencia: 3 }), false)
})

test('resumir los parámetros de una ejecución distingue una de otra', () => {
  assert.equal(
    resumirParametros(PARAMETROS),
    'Bancolombia · Core Bancario — Spring Boot, Java, Inglés B2 — 5+ años',
  )
  assert.match(resumirParametros(null), /no registrados/)
})

// --- HU-15 y HU-22: el doble envío no lanza dos ejecuciones ----------------------

test('un segundo envío mientras el primero sigue en curso no se ejecuta', async () => {
  const guarda = crearGuardaEnvio()
  let llamadas = 0
  let terminar: () => void = () => {}
  const primero = guarda.ejecutar(
    () =>
      new Promise<string>((resolver) => {
        llamadas += 1
        terminar = () => resolver('hecho')
      }),
  )
  // El segundo clic llega antes de que el primero termine, sin un render de por medio.
  const segundo = await guarda.ejecutar(async () => {
    llamadas += 1
    return 'duplicado'
  })

  assert.equal(guarda.activo, true)
  assert.equal(segundo, undefined)
  terminar()
  assert.equal(await primero, 'hecho')
  assert.equal(llamadas, 1)
})

test('al terminar, también si falla, se puede volver a enviar', async () => {
  const guarda = crearGuardaEnvio()
  await assert.rejects(
    guarda.ejecutar(async () => {
      throw new Error('el análisis falló')
    }),
    /el análisis falló/,
  )
  assert.equal(guarda.activo, false)
  assert.equal(await guarda.ejecutar(async () => 'reintento'), 'reintento')
})
