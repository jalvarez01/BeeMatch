import { leerSesion } from '../api/client'
import type { Sesion } from '../types'
import { IconUser } from './Icons'

const ETIQUETA_ROL: Record<string, string> = {
  ADMINISTRADOR: 'Administrador',
  COORDINADOR: 'Coordinador',
  DIRECTOR: 'Director',
}

export default function Topbar({ titulo }: { titulo: string }) {
  const sesion = leerSesion<Sesion>()
  const usuario = sesion?.usuario

  return (
    <header className="bm-topbar">
      <h2>{titulo}</h2>
      <div className="bm-user">
        <span>
          <b>{usuario?.nombre ?? '—'}</b> / {ETIQUETA_ROL[usuario?.rol ?? ''] ?? ''}
        </span>
        <div className="bm-avatar">
          <IconUser />
        </div>
      </div>
    </header>
  )
}
