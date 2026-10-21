import { useState } from 'react'
import { Link } from 'react-router-dom'

import { registrarse } from '../api/auth'

/** HU-03: autorregistro. La cuenta queda pendiente hasta que se apruebe. */
export default function Registro() {
  const [nombre, setNombre] = useState('')
  const [correo, setCorreo] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [registrado, setRegistrado] = useState(false)
  const [cargando, setCargando] = useState(false)

  const enviar = async (evento: React.FormEvent) => {
    evento.preventDefault()
    setCargando(true)
    setError('')
    try {
      await registrarse({ nombre: nombre.trim(), correo: correo.trim(), password })
      setRegistrado(true)
    } catch (excepcion) {
      setError(
        excepcion instanceof TypeError
          ? 'No se pudo conectar con el servidor. Intenta de nuevo.'
          : (excepcion as Error).message,
      )
    } finally {
      setCargando(false)
    }
  }

  return (
    <div className="bm">
      <div className="bm-login">
        <section className="bm-login-left">
          <div className="kicker">
            BeeMatch
            <small>AI Talent Intelligence</small>
          </div>
          <h2>Solicita tu acceso.</h2>
          <p>
            Crea tu cuenta con tu correo corporativo. Un administrador la revisará y te asignará el
            rol antes de que puedas ingresar.
          </p>
        </section>

        <section className="bm-login-right">
          <form className="bm-login-form" onSubmit={enviar}>
            <div style={{ fontSize: 30, fontStyle: 'italic', fontWeight: 700 }}>
              Bee<span style={{ color: '#F5C842' }}>.</span>
            </div>
            <h3>Crear cuenta</h3>

            {registrado ? (
              <>
                <p className="bm-exito">
                  Solicitud enviada. Tu cuenta quedó pendiente de aprobación; podrás ingresar cuando
                  un administrador la active.
                </p>
                <p className="foot">
                  <Link to="/login">Volver al inicio de sesión</Link>
                </p>
              </>
            ) : (
              <>
                <p>Usa tu correo corporativo de BEE.</p>

                <label htmlFor="nombre">Nombre completo</label>
                <input
                  id="nombre"
                  value={nombre}
                  minLength={2}
                  onChange={(e) => setNombre(e.target.value)}
                  required
                />

                <label htmlFor="correo">Correo corporativo</label>
                <input
                  id="correo"
                  type="email"
                  placeholder="nombre@bee.com.co"
                  value={correo}
                  onChange={(e) => setCorreo(e.target.value)}
                  required
                />

                <label htmlFor="password">Contraseña</label>
                <input
                  id="password"
                  type="password"
                  placeholder="Mínimo 8, con letras y números"
                  value={password}
                  minLength={8}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />

                {error && <p className="bm-error">{error}</p>}

                <button type="submit" className="bm-btn bm-btn-primary" disabled={cargando}>
                  {cargando ? 'Enviando…' : 'Solicitar acceso'}
                </button>
                <p className="foot">
                  ¿Ya tienes cuenta? <Link to="/login">Iniciar sesión</Link>
                </p>
              </>
            )}
          </form>
          <span className="copy">© 2026 BEE Consultoría y Negocios</span>
        </section>
      </div>
    </div>
  )
}
