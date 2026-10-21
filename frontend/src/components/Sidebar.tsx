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
  SUPERADMINISTRADOR: [
    { ruta: '/inicio', etiqueta: 'Inicio' },
    { ruta: '/nueva-busqueda', etiqueta: 'Nueva búsqueda' },
    { ruta: '/solicitudes', etiqueta: 'Solicitudes' },
    { ruta: '/usuarios', etiqueta: 'Usuarios' },
    { ruta: '/candidatos', etiqueta: 'Candidatos' },
    { ruta: '/historial', etiqueta: 'Historial' },
  ],
}

/** HU-03-CP5: el módulo de usuarios solo lo ven quienes administran. */
const ROLES_QUE_ADMINISTRAN = ['ADMINISTRADOR', 'SUPERADMINISTRADOR']

export default function Sidebar() {
  const navegar = useNavigate()
  const sesion = leerSesion<Sesion>()
  const rol = sesion?.usuario?.rol
  const navBase = rol ? NAV_POR_ROL[rol] : []
  const puedeAdministrar =
    rol !== undefined && ROLES_QUE_ADMINISTRAN.includes(rol)

  const nav = puedeAdministrar
    ? [
        ...navBase.filter((item) => item.ruta !== '/usuarios'),
        { ruta: '/usuarios', etiqueta: 'Usuarios' },
      ]
    : navBase

  const salir = async () => {
    await cerrarSesion()
    // `replace` saca la pantalla del historial: el botón atrás ya no la muestra.
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
        {puedeAdministrar && (
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
