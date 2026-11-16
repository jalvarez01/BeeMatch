import { useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { cambiarPassword } from '../api/auth'
import { leerSesion } from '../api/client'
import type { Sesion } from '../types'

const MINIMO = 8

/**
 * Cambio de contraseña propio. La superadministradora crea la cuenta con una clave
 * inicial; la persona la cambia aquí y desde ese momento solo ella la conoce.
 */
export default function CambiarPassword() {
  const navegar = useNavigate()
  const obligatorio = Boolean(leerSesion<Sesion>()?.usuario?.debe_cambiar_password)

  const [actual, setActual] = useState('')
  const [nueva, setNueva] = useState('')
  const [repetida, setRepetida] = useState('')
  const [error, setError] = useState('')
  const [enviando, setEnviando] = useState(false)

  const enviar = async (evento: React.FormEvent<HTMLFormElement>) => {
    evento.preventDefault()
    setError('')
    if (nueva.length < MINIMO) {
      setError(`La contraseña nueva debe tener al menos ${MINIMO} caracteres.`)
      return
    }
    if (nueva !== repetida) {
      setError('La contraseña nueva y su confirmación no coinciden.')
      return
    }

    setEnviando(true)
    try {
      await cambiarPassword({ password_actual: actual, password_nueva: nueva })
      navegar('/', { replace: true })
    } catch (e) {
      setError((e as Error).message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <>
      <h1 className="bm-h1">Cambiar contraseña</h1>
      <p className="bm-sub">
        {obligatorio
          ? 'Tu cuenta tiene la contraseña inicial que te dieron. Elige una propia para continuar: nadie más podrá verla.'
          : 'Elige una contraseña nueva. Nadie más podrá verla.'}
      </p>

      {error && (
        <div className="bm-alert bm-alert-error" role="alert">
          {error}
        </div>
      )}

      <form className="bm-card" onSubmit={(e) => void enviar(e)}>
        <div className="bm-field">
          <label htmlFor="cp-actual">Contraseña actual</label>
          <input
            id="cp-actual"
            type="password"
            autoComplete="current-password"
            value={actual}
            onChange={(e) => setActual(e.target.value)}
            required
          />
        </div>
        <div className="bm-field">
          <label htmlFor="cp-nueva">Contraseña nueva</label>
          <input
            id="cp-nueva"
            type="password"
            autoComplete="new-password"
            minLength={MINIMO}
            maxLength={128}
            value={nueva}
            onChange={(e) => setNueva(e.target.value)}
            required
          />
        </div>
        <div className="bm-field">
          <label htmlFor="cp-repetida">Repite la contraseña nueva</label>
          <input
            id="cp-repetida"
            type="password"
            autoComplete="new-password"
            value={repetida}
            onChange={(e) => setRepetida(e.target.value)}
            required
          />
        </div>
        <button
          type="submit"
          className="bm-btn bm-btn-primary"
          style={{ marginTop: 14 }}
          disabled={enviando}
        >
          {enviando ? 'Guardando…' : 'Guardar contraseña'}
        </button>
      </form>
    </>
  )
}
