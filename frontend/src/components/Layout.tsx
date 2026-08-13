import { Navigate, Outlet, useLocation } from 'react-router-dom'

import { leerSesion } from '../api/client'
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
}

function tituloDe(ruta: string): string {
  const coincidencia = Object.keys(TITULOS).find((t) => ruta.startsWith(t))
  return coincidencia ? TITULOS[coincidencia] : 'BeeMatch'
}

/** Envoltura de las pantallas autenticadas. Bloquea el acceso sin sesión. */
export default function Layout() {
  const ubicacion = useLocation()
  const sesion = leerSesion<{ access_token?: string }>()

  if (!sesion?.access_token) {
    return <Navigate to="/login" replace state={{ desde: ubicacion.pathname }} />
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
