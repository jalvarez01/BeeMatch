import { NavLink, useNavigate } from 'react-router-dom'

import { cerrarSesion } from '../api/auth'
import { leerSesion } from '../api/client'
import type { Rol, Sesion } from '../types'

const NAV_POR_ROL: Record<Rol, { ruta: string; etiqueta: string }[]> = {
  COORDINADOR: [
    { ruta: '/nueva-busqueda', etiqueta: 'Nueva búsqueda' },
    { ruta: '/candidatos', etiqueta: 'Candidatos' },
  ],
  DIRECTOR: [
    { ruta: '/nueva-busqueda', etiqueta: 'Nueva búsqueda' },
    { ruta: '/candidatos', etiqueta: 'Candidatos' },
    { ruta: '/historial', etiqueta: 'Historial' },
  ],
  ADMINISTRADOR: [
    { ruta: '/inicio', etiqueta: 'Inicio' },
    { ruta: '/nueva-busqueda', etiqueta: 'Nueva búsqueda' },
    { ruta: '/solicitudes', etiqueta: 'Solicitudes' },
    { ruta: '/usuarios', etiqueta: 'Usuarios' },
    { ruta: '/candidatos', etiqueta: 'Candidatos' },
    { ruta: '/historial', etiqueta: 'Historial' },
  ],
}

export default function Sidebar() {
  const navegar = useNavigate()
  const sesion = leerSesion<Sesion>()
  const rol = sesion?.usuario?.rol
  const nav = rol ? NAV_POR_ROL[rol] : []

  const salir = () => {
    cerrarSesion()
    navegar('/login', { replace: true })
  }

  return (
    <aside className="bm-sidebar">
      <div className="bm-brand">
        <h1>BeeMatch</h1>
        <span>by BEE</span>
      </div>

      <nav className="bm-nav">
        {nav.map((item) => (
          <NavLink key={item.ruta} to={item.ruta}>
            {({ isActive }) => (
              <span data-active={isActive} className="bm-nav-item">
                {item.etiqueta}
              </span>
            )}
          </NavLink>
        ))}
      </nav>

      <div className="bm-sidebar-foot">
        {rol === 'ADMINISTRADOR' && (
          <button className="cfg" onClick={() => navegar('/configuracion')}>
            Configuración
          </button>
        )}
        <button className="out" onClick={salir}>
          Cerrar sesión
        </button>
      </div>
    </aside>
  )
}