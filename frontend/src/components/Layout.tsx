import { useCallback, useEffect } from 'react'
import { Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom'

import { cerrarSesion } from '../api/auth'
import { EVENTO_SESION_EXPIRADA, leerSesion } from '../api/client'
import { MINUTOS_INACTIVIDAD, useInactividad } from '../hooks/useInactividad'
import type { Rol, Sesion } from '../types'
import Sidebar from './Sidebar'
import Topbar from './Topbar'

const TITULOS: Record<string, string> = {
  '/inicio': 'Inicio',
  '/nueva-busqueda': 'Nueva búsqueda',
  '/solicitudes': 'Solicitudes',
  '/candidatos': 'Candidatos',
  '/historial': 'Historial',
  '/resultados': 'Resultados',
  '/candidato': 'Candidato',
  '/configuracion': 'Configuración',
  '/usuarios': 'Usuarios',
}

const RUTAS_POR_ROL: Record<Rol, string[]> = {
  // HU-04: Coordinador solo registra solicitudes y consulta candidatos. Los resultados
  // y el detalle del candidato son parte de ese mismo flujo: la búsqueda termina ahí.
  COORDINADOR: ['/nueva-busqueda', '/candidatos', '/resultados', '/candidato'],
  DIRECTOR: ['/nueva-busqueda', '/candidatos', '/historial', '/resultados', '/candidato'],
  ADMINISTRADOR: [
    '/inicio',
    '/nueva-busqueda',
    '/solicitudes',
    '/usuarios',
    '/candidatos',
    '/historial',
    '/resultados',
    '/candidato',
    '/configuracion',
  ],
  SUPERADMINISTRADOR: [
    '/inicio',
    '/nueva-busqueda',
    '/solicitudes',
    '/usuarios',
    '/candidatos',
    '/historial',
    '/resultados',
    '/candidato',
    '/configuracion',
  ],
}

function tituloDe(ruta: string): string {
  const coincidencia = Object.keys(TITULOS).find((t) => ruta.startsWith(t))
  return coincidencia ? TITULOS[coincidencia] : 'BeeMatch'
}

/** Envoltura de las pantallas autenticadas y control de acceso por rol. */
export default function Layout() {
  const ubicacion = useLocation()

  const navegar = useNavigate()
  const sesion = leerSesion<Sesion>()

  const irAlLogin = useCallback(
    (motivo: string) => navegar('/login', { replace: true, state: { motivo } }),
    [navegar],
  )

  // HU-02-CP4: cierre automático por inactividad, notificando el motivo.
  const porInactividad = useCallback(() => {
    void cerrarSesion().then(() =>
      irAlLogin(`Tu sesión se cerró tras ${MINUTOS_INACTIVIDAD} minutos de inactividad.`),
    )
  }, [irAlLogin])
  useInactividad(porInactividad)

  useEffect(() => {
    // El servidor rechazó el token (venció o la cuenta se inactivó).
    const alExpirar = () => irAlLogin('Tu sesión expiró. Inicia sesión nuevamente.')
    window.addEventListener(EVENTO_SESION_EXPIRADA, alExpirar)

    // HU-02-CP3: comprobar la sesión al volver desde la caché del navegador.
    const alVolver = (evento: PageTransitionEvent) => {
      if (evento.persisted && !leerSesion<Sesion>()?.access_token) {
        window.location.replace('/login')
      }
    }
    window.addEventListener('pageshow', alVolver)

    return () => {
      window.removeEventListener(EVENTO_SESION_EXPIRADA, alExpirar)
      window.removeEventListener('pageshow', alVolver)
    }
  }, [irAlLogin])

  const rol = sesion?.usuario?.rol
  const rutaPermitida = rol
    ? RUTAS_POR_ROL[rol].some(
        (ruta) =>
          ubicacion.pathname === ruta ||
          ubicacion.pathname.startsWith(`${ruta}/`),
      )
    : false

  if (!sesion?.access_token || !rol) {
    return <Navigate to="/login" replace state={{ desde: ubicacion.pathname }} />
  }

  if (!rutaPermitida) {
    const rutaInicial =
      rol === 'ADMINISTRADOR' ? '/inicio' : '/nueva-busqueda'
    return <Navigate to={rutaInicial} replace />
  }

  return (
    <div className="bm">
      <div className="bm-shell">
        <Sidebar />
        <div className="bm-main">
          <Topbar titulo={tituloDe(ubicacion.pathname)} />
          <main className="bm-content">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  )
}
