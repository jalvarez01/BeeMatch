import { NavLink, useNavigate } from 'react-router-dom'

import { cerrarSesion } from '../api/auth'
import { leerSesion } from '../api/client'
import type { Sesion } from '../types'

const NAV = [
  { ruta: '/inicio', etiqueta: 'Inicio' },
  { ruta: '/nueva-busqueda', etiqueta: 'Nueva búsqueda' },
  { ruta: '/solicitudes', etiqueta: 'Solicitudes' },
  { ruta: '/candidatos', etiqueta: 'Candidatos' },
  { ruta: '/historial', etiqueta: 'Historial' },
]

/** HU-03-CP5: el módulo de usuarios solo lo ven quienes administran. */
const ROLES_QUE_ADMINISTRAN = ['ADMINISTRADOR', 'SUPERADMINISTRADOR']

export default function Sidebar() {
  const navegar = useNavigate()
  const rol = leerSesion<Sesion>()?.usuario.rol
  const puedeAdministrar = rol !== undefined && ROLES_QUE_ADMINISTRAN.includes(rol)
  const menu = puedeAdministrar ? [...NAV, { ruta: '/usuarios', etiqueta: 'Usuarios' }] : NAV

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
        {menu.map((item) => (
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
        <button className="cfg" onClick={() => navegar('/configuracion')}>
          Configuración
        </button>
        <button className="out" onClick={salir}>
          Cerrar sesión
        </button>
      </div>
    </aside>
  )
}
