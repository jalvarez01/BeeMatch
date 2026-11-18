import { useCallback, useEffect, useState } from 'react'
import { Navigate } from 'react-router-dom'

import { borrarCliente, crearCliente, listarClientes, renombrarCliente } from '../api/clientes'
import { leerSesion } from '../api/client'
import type { ClienteSugerido, Sesion } from '../types'

const MAXIMO = 100

/**
 * Catálogo de clientes. Solo la superadministradora los registra; las demás personas
 * eligen uno al crear una solicitud.
 */
export default function Clientes() {
  const actor = leerSesion<Sesion>()?.usuario

  const [clientes, setClientes] = useState<ClienteSugerido[]>([])
  const [nombre, setNombre] = useState('')
  const [editando, setEditando] = useState<{ id: string; nombre: string } | null>(null)
  const [cargando, setCargando] = useState(true)
  const [guardando, setGuardando] = useState(false)
  const [mensaje, setMensaje] = useState('')
  const [error, setError] = useState('')

  const cargar = useCallback(async () => {
    setCargando(true)
    try {
      setClientes(await listarClientes('', MAXIMO))
      setError('')
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setCargando(false)
    }
  }, [])

  useEffect(() => {
    void cargar()
  }, [cargar])

  if (actor?.rol !== 'SUPERADMINISTRADOR') {
    return <Navigate to="/inicio" replace />
  }

  const ejecutar = async (accion: () => Promise<unknown>, exito: string) => {
    setError('')
    setMensaje('')
    setGuardando(true)
    try {
      await accion()
      setMensaje(exito)
      await cargar()
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setGuardando(false)
    }
  }

  const crear = (evento: React.FormEvent<HTMLFormElement>) => {
    evento.preventDefault()
    void ejecutar(async () => {
      await crearCliente(nombre.trim())
      setNombre('')
    }, 'Cliente registrado.')
  }

  const guardarNombre = () => {
    if (!editando) return
    void ejecutar(async () => {
      await renombrarCliente(editando.id, editando.nombre.trim())
      setEditando(null)
    }, 'Nombre actualizado.')
  }

  const borrar = (cliente: ClienteSugerido) => {
    if (window.confirm(`¿Borrar el cliente ${cliente.nombre}? Solo se puede si no tiene solicitudes.`)) {
      void ejecutar(() => borrarCliente(cliente.id), 'Cliente borrado.')
    }
  }

  return (
    <>
      <h1 className="bm-h1">Clientes</h1>
      <p className="bm-sub">
        Aquí se registran los clientes de Bee. Quien crea una solicitud solo puede elegir uno de
        esta lista.
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
        <h2 className="bm-h2">Registrar cliente</h2>
        <div className="bm-field">
          <label htmlFor="nc-nombre">Nombre del cliente</label>
          <input
            id="nc-nombre"
            value={nombre}
            minLength={2}
            maxLength={160}
            onChange={(e) => setNombre(e.target.value)}
            required
          />
        </div>
        <button
          type="submit"
          className="bm-btn bm-btn-primary"
          style={{ marginTop: 14 }}
          disabled={guardando}
        >
          {guardando ? 'Guardando…' : 'Registrar cliente'}
        </button>
      </form>

      <section className="bm-card">
        <h2 className="bm-h2">Clientes registrados ({clientes.length})</h2>
        {cargando ? (
          <p>Cargando clientes…</p>
        ) : clientes.length === 0 ? (
          <p>Aún no hay clientes registrados.</p>
        ) : (
          clientes.map((cliente) => (
            <div className="bm-user-row" key={cliente.id}>
              <div>
                {editando?.id === cliente.id ? (
                  <input
                    aria-label="Nombre del cliente"
                    value={editando.nombre}
                    minLength={2}
                    maxLength={160}
                    onChange={(e) => setEditando({ ...editando, nombre: e.target.value })}
                  />
                ) : (
                  <b>{cliente.nombre}</b>
                )}
              </div>
              <span />
              <span />
              <div className="bm-user-acciones">
                {editando?.id === cliente.id ? (
                  <>
                    <button
                      className="bm-btn bm-btn-primary"
                      disabled={guardando}
                      onClick={guardarNombre}
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
                      onClick={() => setEditando({ id: cliente.id, nombre: cliente.nombre })}
                    >
                      Renombrar
                    </button>
                    <button
                      className="bm-btn bm-btn-ghost"
                      disabled={guardando}
                      onClick={() => borrar(cliente)}
                    >
                      Borrar
                    </button>
                  </>
                )}
              </div>
            </div>
          ))
        )}
      </section>
    </>
  )
}
