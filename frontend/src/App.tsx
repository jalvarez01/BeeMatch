import { Navigate, Route, Routes } from 'react-router-dom'

import Layout from './components/Layout'
import Bitacora from './pages/Bitacora'
import Candidato from './pages/Candidato'
import CambiarPassword from './pages/CambiarPassword'
import Candidatos from './pages/Candidatos'
import Clientes from './pages/Clientes'
import Configuracion from './pages/Configuracion'
import Dashboard from './pages/Dashboard'
import Historial from './pages/Historial'
import Login from './pages/Login'
import NuevaBusqueda from './pages/NuevaBusqueda'
import Resultados from './pages/Resultados'
import Solicitudes from './pages/Solicitudes'
import Usuarios from './pages/Usuarios'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />

      <Route element={<Layout />}>
        <Route path="/inicio" element={<Dashboard />} />
        <Route path="/nueva-busqueda" element={<NuevaBusqueda />} />
        <Route path="/solicitudes" element={<Solicitudes />} />
        <Route path="/usuarios" element={<Usuarios />} />
        <Route path="/clientes" element={<Clientes />} />
        <Route path="/bitacora" element={<Bitacora />} />
        <Route path="/candidatos" element={<Candidatos />} />
        <Route path="/historial" element={<Historial />} />
        <Route path="/resultados/:busquedaId" element={<Resultados />} />
        <Route path="/candidato/:recomendacionId" element={<Candidato />} />
        <Route path="/configuracion" element={<Configuracion />} />
        <Route path="/cambiar-password" element={<CambiarPassword />} />
      </Route>

      <Route path="/" element={<Navigate to="/inicio" replace />} />
      <Route path="*" element={<Navigate to="/inicio" replace />} />
    </Routes>
  )
}
