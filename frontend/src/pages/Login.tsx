import { useState } from 'react'
import { useLocation, useNavigate } from 'react-router-dom'

import { iniciarSesion } from '../api/auth'
import { IconEye } from '../components/Icons'

/** HU-01: inicio de sesión con credenciales corporativas. */
export default function Login() {
  const navegar = useNavigate()
  const ubicacion = useLocation()
  const destino = (ubicacion.state as { desde?: string })?.desde ?? '/inicio'

  const [correo, setCorreo] = useState('')
  const [password, setPassword] = useState('')
  const [verClave, setVerClave] = useState(false)
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(false)

  const enviar = async (evento: React.FormEvent) => {
    evento.preventDefault()
    setCargando(true)
    setError('')
    try {
      await iniciarSesion(correo, password)
      navegar(destino, { replace: true })
    } catch (excepcion) {
      // HU-01-CP2: no se indica cuál de los dos datos falló.
      setError('Usuario o contraseña incorrectos')
      void excepcion
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
          <h2>
            Encuentra el talento ideal
            <br />
            para cada proyecto.
          </h2>
          <p>
            BeeMatch analiza hojas de vida con inteligencia artificial para recomendar los perfiles
            con mayor afinidad.
          </p>

          <svg viewBox="0 0 320 278" style={{ marginTop: 'auto', width: '100%' }} aria-hidden>
            <g fill="none" stroke="#F5C842" strokeWidth="1.2">
              <polygon points="45,120 75,103 105,120 105,155 75,172 45,155" />
              <polygon points="120,80 150,63 180,80 180,115 150,132 120,115" />
              <polygon points="85,180 115,163 145,180 145,215 115,232 85,215" />
            </g>
            <g fill="#E8E8EA" fontSize="8" textAnchor="middle">
              <text x="75" y="135">Recomendaciones</text>
              <text x="75" y="145">inteligentes</text>
              <text x="150" y="95">Análisis de hojas</text>
              <text x="150" y="105">de vida</text>
              <text x="115" y="195">Staffing ágil</text>
              <text x="115" y="205">y preciso</text>
            </g>
            {/* La curva pasa por debajo del hexágono inferior: no debe cruzarlo. */}
            <path d="M15 258 Q115 262 205 204 T305 118" fill="none" stroke="#6E6E73" strokeWidth="1.2" />
            {/* Los cuatro puntos caen exactamente sobre la curva:
                inicio, punto medio del primer tramo, unión de tramos y final. */}
            <circle cx="15" cy="258" r="4" fill="#D9D9DC" />
            <circle cx="112.5" cy="246.5" r="4" fill="#D9D9DC" />
            <circle cx="205" cy="204" r="4" fill="#F5C842" />
            <circle cx="305" cy="118" r="4" fill="#D9D9DC" />
          </svg>
        </section>

        <section className="bm-login-right">
          <form className="bm-login-form" onSubmit={enviar}>
            <div style={{ fontSize: 30, fontStyle: 'italic', fontWeight: 700 }}>
              Bee<span style={{ color: '#F5C842' }}>.</span>
            </div>
            <h3>Bienvenido de nuevo</h3>
            <p>Ingresa con tus credenciales corporativas de BEE.</p>

            <label htmlFor="correo">Correo corporativo</label>
            <input
              id="correo"
              type="email"
              placeholder="nombre@bee.com.co"
              value={correo}
              data-error={Boolean(error)}
              onChange={(e) => setCorreo(e.target.value)}
              required
            />

            <label htmlFor="password">Contraseña</label>
            <div className="bm-input-wrap">
              <input
                id="password"
                type={verClave ? 'text' : 'password'}
                placeholder="••••••••••"
                value={password}
                data-error={Boolean(error)}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
              <button
                type="button"
                className="bm-eye"
                onClick={() => setVerClave(!verClave)}
                aria-label="Mostrar contraseña"
              >
                <IconEye />
              </button>
            </div>

            {error && <p className="bm-error">{error}</p>}

            <button type="submit" className="bm-btn bm-btn-primary" disabled={cargando}>
              {cargando ? 'Ingresando…' : 'Iniciar sesión'}
            </button>
            <p className="foot">Acceso exclusivo para personal autorizado de BEE.</p>
          </form>
          <span className="copy">© 2026 BEE Consultoría y Negocios</span>
        </section>
      </div>
    </div>
  )
}