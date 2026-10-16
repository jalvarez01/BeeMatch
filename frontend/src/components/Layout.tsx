import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { leerSesion } from '../api/client'
import type { Rol, Sesion } from '../types'
import Sidebar from './Sidebar'
import Topbar from './Topbar'

const TITULOS: Record<string, string> = {
  '/inicio': 'Inicio',
  '/nueva-busqueda': 'Nueva búsqueda',
  '/solicitudes': 'Solicitudes',
  '/usuarios': 'Gestión de usuarios',
  '/candidatos': 'Candidatos',
  '/historial': 'Historial',
  '/resultados': 'Resultados',
  '/candidato': 'Candidato',
  '/configuracion': 'Configuración',
}

const RUTAS_POR_ROL: Record<Rol, string[]> = {
  COORDINADOR: ['/nueva-busqueda', '/candidatos'],
  DIRECTOR: ['/nueva-busqueda', '/candidatos', '/historial'],
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
}

function tituloDe(ruta: string): string {
  const coincidencia = Object.keys(TITULOS).find((t) => ruta.startsWith(t))
  return coincidencia ? TITULOS[coincidencia] : 'BeeMatch'
}

/** Envoltura de las pantallas autenticadas y control de acceso por rol. */
export default function Layout() {
  const ubicacion = useLocation()
  const sesion = leerSesion<Sesion>()
  const rol = sesion?.usuario?.rol
  const rutaPermitida = rol
    ? RUTAS_POR_ROL[rol].some((ruta) => ubicacion.pathname === ruta || ubicacion.pathname.startsWith(`${ruta}/`))
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