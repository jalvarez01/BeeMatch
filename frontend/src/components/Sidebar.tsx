import { NavLink, useNavigate } from 'react-router-dom'

import { cerrarSesion } from '../api/auth'

const NAV = [
  { ruta: '/inicio', etiqueta: 'Inicio' },
  { ruta: '/nueva-busqueda', etiqueta: 'Nueva búsqueda' },
  { ruta: '/solicitudes', etiqueta: 'Solicitudes' },
  { ruta: '/candidatos', etiqueta: 'Candidatos' },
  { ruta: '/historial', etiqueta: 'Historial' },
]

export default function Sidebar() {
  const navegar = useNavigate()

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
        {NAV.map((item) => (
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
