import { useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'

import { leerSesion } from '../api/client'
import {
  actualizarUsuario,
  crearUsuario,
  listarUsuarios,
  type CambiosUsuario,
  type NuevoUsuario,
} from '../api/usuarios'
import type { Rol, Sesion, Usuario } from '../types'

const ETIQUETA_ROL: Record<Rol, string> = {
  SUPERADMINISTRADOR: 'Superadministradora',
  ADMINISTRADOR: 'Administrador',
  COORDINADOR: 'Coordinador',
  DIRECTOR: 'Director',
}

/** Roles que cada actor puede otorgar. Espeja `ROLES_QUE_GESTIONA` del backend. */
const ROLES_QUE_GESTIONA: Partial<Record<Rol, Rol[]>> = {
  SUPERADMINISTRADOR: ['COORDINADOR', 'DIRECTOR', 'ADMINISTRADOR'],
  ADMINISTRADOR: ['COORDINADOR', 'DIRECTOR'],
}

const FORMULARIO_VACIO: NuevoUsuario = { nombre: '', correo: '', password: '', rol: 'COORDINADOR' }

/** HU-03: creación, edición, aprobación e inactivación de usuarios. */
export default function Usuarios() {
  const actor = leerSesion<Sesion>()?.usuario
  const gestionables = (actor && ROLES_QUE_GESTIONA[actor.rol]) ?? []

  const [usuarios, setUsuarios] = useState<Usuario[]>([])
  const [formulario, setFormulario] = useState<NuevoUsuario>(FORMULARIO_VACIO)
  const [editando, setEditando] = useState<{ id: string; nombre: string; correo: string } | null>(
    null,
  )
  const [mensaje, setMensaje] = useState('')
  const [error, setError] = useState('')

  const cargar = () =>
    listarUsuarios()
      .then(setUsuarios)
      .catch((e: Error) => setError(e.message))

  useEffect(() => {
    void cargar()
  }, [])

  // HU-03-CP5: Coordinador y Director no ven este módulo ni entrando por URL.
  if (!actor || gestionables.length === 0) return <Navigate to="/inicio" replace />

  const puedeGestionar = (objetivo: Usuario) => gestionables.includes(objetivo.rol)

  const ejecutar = async (accion: () => Promise<unknown>, exito: string) => {
    setError('')
    setMensaje('')
    try {
      await accion()
      setMensaje(exito)
      await cargar()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const crear = (evento: React.FormEvent) => {
    evento.preventDefault()
    void ejecutar(async () => {
      await crearUsuario({ ...formulario, nombre: formulario.nombre.trim() })
      setFormulario(FORMULARIO_VACIO)
    }, 'Usuario creado. Ya puede iniciar sesión.')
  }

  const cambiar = (usuario: Usuario, cambios: CambiosUsuario, exito: string) =>
    ejecutar(() => actualizarUsuario(usuario.id, cambios), exito)

  const guardarEdicion = () => {
    if (!editando) return
    void ejecutar(async () => {
      await actualizarUsuario(editando.id, {
        nombre: editando.nombre.trim(),
        correo: editando.correo.trim(),
      })
      setEditando(null)
    }, 'Datos actualizados.')
  }

  const pendientes = usuarios.filter((u) => u.pendiente)
  const resto = usuarios.filter((u) => !u.pendiente)

  const fila = (usuario: Usuario) => (
    <div className="bm-user-row" key={usuario.id}>
      <div>
        {editando?.id === usuario.id ? (
          <div style={{ display: 'grid', gap: 6 }}>
            <input
              aria-label="Nombre"
              value={editando.nombre}
              onChange={(e) => setEditando({ ...editando, nombre: e.target.value })}
            />
            <input
              aria-label="Correo"
              type="email"
              value={editando.correo}
              onChange={(e) => setEditando({ ...editando, correo: e.target.value })}
            />
          </div>
        ) : (
          <>
            <div style={{ fontSize: 13, fontWeight: 600 }}>{usuario.nombre}</div>
            <div style={{ fontSize: 12, color: 'var(--muted)' }}>{usuario.correo}</div>
          </>
        )}
      </div>

      <div>
        {puedeGestionar(usuario) ? (
          <select
            aria-label={`Rol de ${usuario.nombre}`}
            value={usuario.rol}
            onChange={(e) =>
              void cambiar(usuario, { rol: e.target.value as CambiosUsuario['rol'] }, 'Rol actualizado.')
            }
          >
            {gestionables.map((rol) => (
              <option key={rol} value={rol}>
                {ETIQUETA_ROL[rol]}
              </option>
            ))}
          </select>
        ) : (
          <span style={{ fontSize: 12 }}>{ETIQUETA_ROL[usuario.rol]}</span>
        )}
      </div>

      <span
        className={`bm-badge ${
          usuario.pendiente ? 'bm-badge-yellow' : usuario.activo ? 'bm-badge-green' : 'bm-badge-gray'
        }`}
      >
        {usuario.pendiente ? 'Pendiente' : usuario.activo ? 'Activo' : 'Inactivo'}
      </span>

      <div className="bm-user-acciones">
        {puedeGestionar(usuario) &&
          (editando?.id === usuario.id ? (
            <>
              <button className="bm-btn bm-btn-primary" onClick={guardarEdicion}>
                Guardar
              </button>
              <button className="bm-btn bm-btn-ghost" onClick={() => setEditando(null)}>
                Cancelar
              </button>
            </>
          ) : (
            <>
              <button
                className="bm-btn bm-btn-ghost"
                onClick={() =>
                  setEditando({ id: usuario.id, nombre: usuario.nombre, correo: usuario.correo })
                }
              >
                Editar
              </button>
              {usuario.pendiente ? (
                <>
                  <button
                    className="bm-btn bm-btn-primary"
                    onClick={() => void cambiar(usuario, { activo: true }, 'Cuenta aprobada.')}
                  >
                    Aprobar
                  </button>
                  <button
                    className="bm-btn bm-btn-ghost"
                    onClick={() => void cambiar(usuario, { activo: false }, 'Solicitud rechazada.')}
                  >
                    Rechazar
                  </button>
                </>
              ) : usuario.activo ? (
                <button
                  className="bm-btn bm-btn-ghost"
                  onClick={() => void cambiar(usuario, { activo: false }, 'Usuario inactivado.')}
                >
                  Inactivar
                </button>
              ) : (
                <button
                  className="bm-btn bm-btn-ghost"
                  onClick={() => void cambiar(usuario, { activo: true }, 'Usuario reactivado.')}
                >
                  Reactivar
                </button>
              )}
            </>
          ))}
      </div>
    </div>
  )

  return (
    <>
      <h1 className="bm-h1">Usuarios</h1>
      <p className="bm-sub">
        Crea, edita e inactiva cuentas. Al inactivar se impide el acceso pero se conserva el
        historial.
      </p>

      {error && <div className="bm-alert bm-alert-error">{error}</div>}
      {mensaje && <div className="bm-alert bm-alert-info">{mensaje}</div>}

      <form className="bm-card" onSubmit={crear}>
        <h2 className="bm-h2">Nuevo usuario</h2>
        <div className="bm-grid2">
          <div className="bm-field">
            <label htmlFor="nu-nombre">Nombre</label>
            <input
              id="nu-nombre"
              value={formulario.nombre}
              minLength={2}
              onChange={(e) => setFormulario({ ...formulario, nombre: e.target.value })}
              required
            />
          </div>
          <div className="bm-field">
            <label htmlFor="nu-correo">Correo corporativo</label>
            <input
              id="nu-correo"
              type="email"
              placeholder="nombre@bee.com.co"
              value={formulario.correo}
              onChange={(e) => setFormulario({ ...formulario, correo: e.target.value })}
              required
            />
          </div>
          <div className="bm-field">
            <label htmlFor="nu-password">Contraseña inicial</label>
            <input
              id="nu-password"
              type="password"
              placeholder="Mínimo 8, con letras y números"
              value={formulario.password}
              minLength={8}
              onChange={(e) => setFormulario({ ...formulario, password: e.target.value })}
              required
            />
          </div>
          <div className="bm-field">
            <label htmlFor="nu-rol">Rol</label>
            <select
              id="nu-rol"
              value={formulario.rol}
              onChange={(e) =>
                setFormulario({ ...formulario, rol: e.target.value as NuevoUsuario['rol'] })
              }
            >
              {gestionables.map((rol) => (
                <option key={rol} value={rol}>
                  {ETIQUETA_ROL[rol]}
                </option>
              ))}
            </select>
          </div>
        </div>
        <button type="submit" className="bm-btn bm-btn-primary" style={{ marginTop: 14 }}>
          Crear usuario
        </button>
      </form>

      {pendientes.length > 0 && (
        <div className="bm-card">
          <h2 className="bm-h2">Solicitudes de acceso ({pendientes.length})</h2>
          {pendientes.map(fila)}
        </div>
      )}

      <div className="bm-card">
        <h2 className="bm-h2">Usuarios</h2>
        {resto.map(fila)}
      </div>
    </>
  )
}
