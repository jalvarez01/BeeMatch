import { useCallback, useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'

import { leerSesion } from '../api/client'
import {
  actualizarUsuario,
  crearUsuario,
  listarUsuarios,
} from '../api/usuarios'
import type { CambiosUsuario, CrearUsuarioPayload } from '../api/usuarios'
import type { Rol, Sesion, Usuario } from '../types'

const ETIQUETA_ROL: Record<Rol, string> = {
  SUPERADMINISTRADOR: 'Superadministrador',
  ADMINISTRADOR: 'Administrador',
  COORDINADOR: 'Coordinador',
  DIRECTOR: 'Director',
}

/** Roles que cada actor puede otorgar. Debe coincidir con el backend. */
const ROLES_QUE_GESTIONA: Partial<Record<Rol, Rol[]>> = {
  SUPERADMINISTRADOR: ['COORDINADOR', 'DIRECTOR', 'ADMINISTRADOR'],
  ADMINISTRADOR: ['COORDINADOR', 'DIRECTOR'],
}

const FORMULARIO_VACIO: CrearUsuarioPayload = {
  nombre: '',
  correo: '',
  password: '',
  rol: 'COORDINADOR',
}

/** HU-03: creación, edición, aprobación e inactivación de usuarios. */
export default function Usuarios() {
  const actor = leerSesion<Sesion>()?.usuario
  const gestionables = (actor && ROLES_QUE_GESTIONA[actor.rol]) ?? []

  const [usuarios, setUsuarios] = useState<Usuario[]>([])
  const [formulario, setFormulario] =
    useState<CrearUsuarioPayload>(FORMULARIO_VACIO)
  const [editando, setEditando] = useState<{
    id: string
    nombre: string
    correo: string
  } | null>(null)
  const [cargando, setCargando] = useState(true)
  const [guardando, setGuardando] = useState(false)
  const [mensaje, setMensaje] = useState('')
  const [error, setError] = useState('')

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

  // HU-03-CP5: Coordinador y Director no pueden acceder al módulo.
  if (!actor || gestionables.length === 0) {
    return <Navigate to="/inicio" replace />
  }

  const puedeGestionar = (objetivo: Usuario) =>
    gestionables.includes(objetivo.rol)

  const ejecutar = async (
    accion: () => Promise<unknown>,
    exito: string,
  ) => {
    setError('')
    setMensaje('')
    setGuardando(true)

    try {
      await accion()
      setMensaje(exito)
      await cargarUsuarios()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setGuardando(false)
    }
  }

  const crear = (evento: React.FormEvent<HTMLFormElement>) => {
    evento.preventDefault()

    void ejecutar(async () => {
      await crearUsuario({
        ...formulario,
        nombre: formulario.nombre.trim(),
        correo: formulario.correo.trim(),
      })
      setFormulario(FORMULARIO_VACIO)
    }, 'Usuario creado correctamente.')
  }

  const cambiar = (
    usuario: Usuario,
    cambios: CambiosUsuario,
    exito: string,
  ) => ejecutar(() => actualizarUsuario(usuario.id, cambios), exito)

  const guardarEdicion = () => {
    if (!editando) return

    void ejecutar(async () => {
      await actualizarUsuario(editando.id, {
        nombre: editando.nombre.trim(),
        correo: editando.correo.trim(),
      })
      setEditando(null)
    }, 'Datos actualizados correctamente.')
  }

  const pendientes = usuarios.filter((usuario) => usuario.pendiente)
  const resto = usuarios.filter((usuario) => !usuario.pendiente)

  const fila = (usuario: Usuario) => (
    <div className="bm-user-row" key={usuario.id}>
      <div>
        {editando?.id === usuario.id ? (
          <div style={{ display: 'grid', gap: 6 }}>
            <input
              aria-label="Nombre"
              value={editando.nombre}
              minLength={2}
              maxLength={160}
              onChange={(e) =>
                setEditando({ ...editando, nombre: e.target.value })
              }
            />
            <input
              aria-label="Correo"
              type="email"
              pattern="^[^@\s]+@bee\.com\.co$"
              title="Solo se permiten correos con dominio @bee.com.co"
              value={editando.correo}
              onChange={(e) =>
                setEditando({ ...editando, correo: e.target.value })
              }
            />
          </div>
        ) : (
          <>
            <div style={{ fontSize: 13, fontWeight: 600 }}>
              {usuario.nombre}
            </div>
            <div style={{ fontSize: 12, color: 'var(--muted)' }}>
              {usuario.correo}
            </div>
          </>
        )}
      </div>

      <div>
        {puedeGestionar(usuario) ? (
          <select
            aria-label={`Rol de ${usuario.nombre}`}
            value={usuario.rol}
            disabled={!usuario.activo || guardando}
            onChange={(e) =>
              void cambiar(
                usuario,
                { rol: e.target.value as CambiosUsuario['rol'] },
                `Rol actualizado para ${usuario.nombre}.`,
              )
            }
          >
            <option value={usuario.rol}>
              {ETIQUETA_ROL[usuario.rol]}
            </option>
            {gestionables
              .filter((rol) => rol !== usuario.rol)
              .map((rol) => (
                <option key={rol} value={rol}>
                  {ETIQUETA_ROL[rol]}
                </option>
              ))}
          </select>
        ) : (
          <span style={{ fontSize: 12 }}>
            {ETIQUETA_ROL[usuario.rol]}
          </span>
        )}
      </div>

      <span
        className={`bm-badge ${
          usuario.pendiente
            ? 'bm-badge-yellow'
            : usuario.activo
              ? 'bm-badge-green'
              : 'bm-badge-gray'
        }`}
      >
        {usuario.pendiente
          ? 'Pendiente'
          : usuario.activo
            ? 'Activo'
            : 'Inactivo'}
      </span>

      <div className="bm-user-acciones">
        {puedeGestionar(usuario) &&
          (editando?.id === usuario.id ? (
            <>
              <button
                className="bm-btn bm-btn-primary"
                disabled={guardando}
                onClick={guardarEdicion}
              >
                Guardar
              </button>
              <button
                className="bm-btn bm-btn-ghost"
                disabled={guardando}
                onClick={() => setEditando(null)}
              >
                Cancelar
              </button>
            </>
          ) : (
            <>
              <button
                className="bm-btn bm-btn-ghost"
                disabled={guardando}
                onClick={() =>
                  setEditando({
                    id: usuario.id,
                    nombre: usuario.nombre,
                    correo: usuario.correo,
                  })
                }
              >
                Editar
              </button>

              {usuario.pendiente ? (
                <>
                  <button
                    className="bm-btn bm-btn-primary"
                    disabled={guardando}
                    onClick={() =>
                      void cambiar(
                        usuario,
                        { activo: true },
                        'Cuenta aprobada.',
                      )
                    }
                  >
                    Aprobar
                  </button>
                  <button
                    className="bm-btn bm-btn-ghost"
                    disabled={guardando}
                    onClick={() =>
                      void cambiar(
                        usuario,
                        { activo: false },
                        'Solicitud rechazada.',
                      )
                    }
                  >
                    Rechazar
                  </button>
                </>
              ) : usuario.activo ? (
                <button
                  className="bm-btn bm-btn-ghost"
                  disabled={guardando}
                  onClick={() =>
                    void cambiar(
                      usuario,
                      { activo: false },
                      'Usuario inactivado.',
                    )
                  }
                >
                  Inactivar
                </button>
              ) : (
                <button
                  className="bm-btn bm-btn-ghost"
                  disabled={guardando}
                  onClick={() =>
                    void cambiar(
                      usuario,
                      { activo: true },
                      'Usuario reactivado.',
                    )
                  }
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
      <h1 className="bm-h1">Gestión de usuarios</h1>
      <p className="bm-sub">
        Crea, edita e inactiva cuentas. Al inactivar se impide el acceso,
        pero se conserva el historial.
      </p>

      {error && (
        <div className="bm-alert bm-alert-error" role="alert">
          {error}
        </div>
      )}
      {mensaje && (
        <div className="bm-alert bm-alert-info" role="status">
          {mensaje}
        </div>
      )}

      <form className="bm-card" onSubmit={crear}>
        <h2 className="bm-h2">Crear usuario</h2>

        <div className="bm-grid2">
          <div className="bm-field">
            <label htmlFor="nu-nombre">Nombre</label>
            <input
              id="nu-nombre"
              value={formulario.nombre}
              minLength={2}
              maxLength={160}
              onChange={(e) =>
                setFormulario({ ...formulario, nombre: e.target.value })
              }
              required
            />
          </div>

          <div className="bm-field">
            <label htmlFor="nu-correo">Correo corporativo</label>
            <input
              id="nu-correo"
              type="email"
              pattern="^[^@\s]+@bee\.com\.co$"
              title="Solo se permiten correos con dominio @bee.com.co"
              placeholder="nombre@bee.com.co"
              value={formulario.correo}
              onChange={(e) =>
                setFormulario({ ...formulario, correo: e.target.value })
              }
              required
            />
          </div>

          <div className="bm-field">
            <label htmlFor="nu-password">Contraseña inicial</label>
            <input
              id="nu-password"
              type="password"
              value={formulario.password}
              minLength={8}
              maxLength={128}
              autoComplete="new-password"
              onChange={(e) =>
                setFormulario({ ...formulario, password: e.target.value })
              }
              required
            />
          </div>

          <div className="bm-field">
            <label htmlFor="nu-rol">Rol inicial</label>
            <select
              id="nu-rol"
              value={formulario.rol}
              onChange={(e) =>
                setFormulario({
                  ...formulario,
                  rol: e.target.value as CrearUsuarioPayload['rol'],
                })
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

        <button
          type="submit"
          className="bm-btn bm-btn-primary"
          style={{ marginTop: 14 }}
          disabled={guardando}
        >
          {guardando ? 'Guardando…' : 'Crear usuario'}
        </button>
      </form>

      {pendientes.length > 0 && (
        <section className="bm-card">
          <h2 className="bm-h2">
            Solicitudes de acceso ({pendientes.length})
          </h2>
          {pendientes.map(fila)}
        </section>
      )}

      <section className="bm-card">
        <div className="bm-row-between">
          <h2 className="bm-h2">Usuarios registrados</h2>
          <button
            type="button"
            className="bm-btn bm-btn-ghost"
            disabled={cargando}
            onClick={() => void cargarUsuarios()}
          >
            Actualizar
          </button>
        </div>

        {cargando ? (
          <p>Cargando usuarios…</p>
        ) : resto.length === 0 ? (
          <p>No hay usuarios registrados.</p>
        ) : (
          resto.map(fila)
        )}
      </section>
    </>
  )
}