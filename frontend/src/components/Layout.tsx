import { useCallback, useEffect } from 'react'
import { Navigate, Outlet, useLocation, useNavigate } from 'react-router-dom'

import { cerrarSesion } from '../api/auth'
import { EVENTO_SESION_EXPIRADA, leerSesion } from '../api/client'
import { MINUTOS_INACTIVIDAD, useInactividad } from '../hooks/useInactividad'
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

function tituloDe(ruta: string): string {
  const coincidencia = Object.keys(TITULOS).find((t) => ruta.startsWith(t))
  return coincidencia ? TITULOS[coincidencia] : 'BeeMatch'
}

/** Envoltura de las pantallas autenticadas. Bloquea el acceso sin sesión. */
export default function Layout() {
  const ubicacion = useLocation()
  const navegar = useNavigate()
  const sesion = leerSesion<{ access_token?: string }>()

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

    // HU-02-CP3: con el botón atrás el navegador puede restaurar la pantalla
    // desde su caché sin volver a ejecutar nada; se vuelve a comprobar la sesión.
    const alVolver = (evento: PageTransitionEvent) => {
      if (evento.persisted && !leerSesion<{ access_token?: string }>()?.access_token) {
        window.location.replace('/login')
      }
    }
    window.addEventListener('pageshow', alVolver)

    return () => {
      window.removeEventListener(EVENTO_SESION_EXPIRADA, alExpirar)
      window.removeEventListener('pageshow', alVolver)
    }
  }, [irAlLogin])

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
