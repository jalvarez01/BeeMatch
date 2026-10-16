import { useCallback, useEffect, useState } from 'react'
import {
  actualizarUsuario,
  crearUsuario,
  listarUsuarios,
} from '../api/usuarios'
import type { Rol, Usuario } from '../types'

const ROLES: Rol[] = ['COORDINADOR', 'DIRECTOR', 'ADMINISTRADOR']

export default function Usuarios() {
  const [usuarios, setUsuarios] = useState<Usuario[]>([])
  const [nombre, setNombre] = useState('')
  const [correo, setCorreo] = useState('')
  const [password, setPassword] = useState('')
  const [rol, setRol] = useState<Rol>('COORDINADOR')
  const [cargando, setCargando] = useState(true)
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')
  const [mensaje, setMensaje] = useState('')

  const cargarUsuarios = useCallback(async () => {
    setCargando(true)
    try {
      setUsuarios(await listarUsuarios())
      setError('')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setCargando(false)
    }
  }, [])

  useEffect(() => {
    void cargarUsuarios()
  }, [cargarUsuarios])

  const crear = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault()
    setGuardando(true)
    setError('')
    setMensaje('')

    try {
      await crearUsuario({ nombre: nombre.trim(), correo: correo.trim(), password, rol })
      setNombre('')
      setCorreo('')
      setPassword('')
      setRol('COORDINADOR')
      setMensaje('Usuario creado correctamente.')
      await cargarUsuarios()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setGuardando(false)
    }
  }

  const cambiarRol = async (usuario: Usuario, nuevoRol: Rol) => {
    if (usuario.rol === nuevoRol) return
    setError('')
    setMensaje('')

    try {
      await actualizarUsuario(usuario.id, { rol: nuevoRol })
      setMensaje(`Rol actualizado para ${usuario.nombre}. El cambio de permisos se aplicará en su próximo inicio de sesión.`)
      await cargarUsuarios()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const cambiarEstado = async (usuario: Usuario) => {
    const nuevoEstado = !usuario.activo
    if (!window.confirm(
      `${nuevoEstado ? '¿Activar' : '¿Desactivar'} la cuenta de ${usuario.nombre}?`,
    )) return

    setError('')
    setMensaje('')

    try {
      await actualizarUsuario(usuario.id, { activo: nuevoEstado })
      setMensaje(`Cuenta de ${usuario.nombre} ${nuevoEstado ? 'activada' : 'desactivada'}.`)
      await cargarUsuarios()
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <>
      <h1 className="bm-h1">Gestión de usuarios</h1>
      <p className="bm-sub">
        Crea cuentas y administra roles y acceso a BeeMatch.
      </p>

      {error && <div className="bm-alert bm-alert-error" role="alert">{error}</div>}
      {mensaje && <div className="bm-alert bm-alert-info" role="status">{mensaje}</div>}

      <section className="bm-card">
        <h2 className="bm-h2">Crear usuario</h2>
        <form onSubmit={crear}>
          <div className="bm-grid2">
            <div className="bm-field">
              <label htmlFor="usuario-nombre">Nombre</label>
              <input
                id="usuario-nombre"
                value={nombre}
                onChange={(e) => setNombre(e.target.value)}
                minLength={2}
                maxLength={160}
                required
              />
            </div>
            <div className="bm-field">
              <label htmlFor="usuario-correo">Correo</label>
              <input
                id="usuario-correo"
                type="email"
                pattern="^[^@\s]+@bee\.com\.co$"
                title="Solo se permiten correos con dominio @bee.com.co"
                value={correo}
                onChange={(e) => setCorreo(e.target.value)}
                required
              />
            </div>
            <div className="bm-field">
              <label htmlFor="usuario-password">Contraseña inicial</label>
              <input
                id="usuario-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                minLength={8}
                maxLength={128}
                autoComplete="new-password"
                required
              />
            </div>
            <div className="bm-field">
              <label htmlFor="usuario-rol">Rol inicial</label>
              <select
                id="usuario-rol"
                value={rol}
                onChange={(e) => setRol(e.target.value as Rol)}
              >
                {ROLES.map((opcion) => (
                  <option key={opcion} value={opcion}>{opcion}</option>
                ))}
              </select>
            </div>
          </div>
          <button className="bm-btn bm-btn-primary" type="submit" disabled={guardando}>
            {guardando ? 'Creando…' : 'Crear usuario'}
          </button>
        </form>
      </section>

      <section className="bm-card">
        <div className="bm-row-between">
          <h2 className="bm-h2">Usuarios registrados</h2>
          <button className="bm-btn bm-btn-ghost" onClick={() => void cargarUsuarios()}>
            Actualizar
          </button>
        </div>

        {cargando ? (
          <p>Cargando usuarios…</p>
        ) : usuarios.length === 0 ? (
          <p>No hay usuarios registrados.</p>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
              <thead>
                <tr>
                  <th style={{ padding: 10 }}>Usuario</th>
                  <th style={{ padding: 10 }}>Rol</th>
                  <th style={{ padding: 10 }}>Estado</th>
                  <th style={{ padding: 10 }}>Acciones</th>
                </tr>
              </thead>
              <tbody>
                {usuarios.map((usuario) => (
                  <tr key={usuario.id} style={{ borderTop: '1px solid var(--border)' }}>
                    <td style={{ padding: 10 }}>
                      <strong>{usuario.nombre}</strong>
                      <div style={{ fontSize: 12, color: 'var(--muted)' }}>{usuario.correo}</div>
                    </td>
                    <td style={{ padding: 10 }}>
                      <select
                        aria-label={`Rol de ${usuario.nombre}`}
                        value={usuario.rol}
                        disabled={!usuario.activo}
                        onChange={(e) => void cambiarRol(usuario, e.target.value as Rol)}
                      >
                        {ROLES.map((opcion) => (
                          <option key={opcion} value={opcion}>{opcion}</option>
                        ))}
                      </select>
                    </td>
                    <td style={{ padding: 10 }}>
                      {usuario.activo ? 'Activo' : 'Inactivo'}
                    </td>
                    <td style={{ padding: 10 }}>
                      <button
                        className="bm-btn bm-btn-ghost"
                        onClick={() => void cambiarEstado(usuario)}
                      >
                        {usuario.activo ? 'Desactivar' : 'Activar'}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </>
  )
}