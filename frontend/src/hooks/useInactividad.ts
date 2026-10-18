import { useEffect } from 'react'

import { renovarSesion } from '../api/auth'

/** HU-02: minutos sin actividad tras los cuales se cierra la sesión. */
export const MINUTOS_INACTIVIDAD = 30

const CLAVE_ACTIVIDAD = 'beematch_ultima_actividad'
const REVISION_MS = 30_000
// El token dura lo mismo que la inactividad permitida; se renueva con la
// actividad, a lo sumo cada 5 minutos para no llenar el servidor de llamadas.
const RENOVACION_MS = 5 * 60_000
const EVENTOS = ['mousedown', 'keydown', 'scroll', 'touchstart', 'mousemove'] as const

function leerActividad(): number {
  try {
    return Number(localStorage.getItem(CLAVE_ACTIVIDAD)) || Date.now()
  } catch {
    return Date.now()
  }
}

function marcarActividad(): void {
  try {
    localStorage.setItem(CLAVE_ACTIVIDAD, String(Date.now()))
  } catch {
    // Sin almacenamiento solo se pierde la coordinación entre pestañas.
  }
}

/**
 * Cierra la sesión tras 30 minutos sin actividad y mantiene vigente el token
 * mientras el usuario trabaja. La última actividad se guarda en localStorage y
 * se compara con la hora real: así también se respeta cuando el equipo estuvo
 * suspendido (los temporizadores se pausan) o hay varias pestañas abiertas.
 */
export function useInactividad(alExpirar: () => void): void {
  useEffect(() => {
    marcarActividad()
    let ultimaRenovacion = Date.now()

    const alActividad = () => {
      const ahora = Date.now()
      marcarActividad()
      if (ahora - ultimaRenovacion > RENOVACION_MS) {
        ultimaRenovacion = ahora
        renovarSesion().catch(() => undefined)
      }
    }

    const revisar = () => {
      if (Date.now() - leerActividad() > MINUTOS_INACTIVIDAD * 60_000) alExpirar()
    }

    EVENTOS.forEach((evento) => window.addEventListener(evento, alActividad, { passive: true }))
    const temporizador = setInterval(revisar, REVISION_MS)
    window.addEventListener('focus', revisar)

    return () => {
      EVENTOS.forEach((evento) => window.removeEventListener(evento, alActividad))
      clearInterval(temporizador)
      window.removeEventListener('focus', revisar)
    }
  }, [alExpirar])
}
