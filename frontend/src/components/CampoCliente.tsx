import { useEffect, useRef, useState } from 'react'

import { listarClientes } from '../api/clientes'
import type { ClienteSugerido } from '../types'

const ESPERA_MS = 250

interface Props {
  id: string
  valor: string
  onCambio: (valor: string) => void
  deshabilitado?: boolean
  atributosError?: Pick<React.InputHTMLAttributes<HTMLInputElement>, 'aria-invalid' | 'aria-describedby'>
}

/**
 * HU-12: campo de cliente con sugerencias. Al escribir las primeras letras ofrece los
 * clientes ya registrados; elegir uno evita duplicarlo. Si no hay coincidencia, lo
 * escrito se registra como cliente nuevo al guardar. Si las sugerencias fallan el
 * campo sigue funcionando como texto libre.
 */
export default function CampoCliente({ id, valor, onCambio, deshabilitado, atributosError }: Props) {
  const [sugerencias, setSugerencias] = useState<ClienteSugerido[]>([])
  const [abierto, setAbierto] = useState(false)
  const [activa, setActiva] = useState(-1)
  const temporizador = useRef<ReturnType<typeof setTimeout> | null>(null)
  const peticion = useRef<AbortController | null>(null)

  useEffect(
    () => () => {
      if (temporizador.current) clearTimeout(temporizador.current)
      peticion.current?.abort()
    },
    [],
  )

  const buscar = (texto: string) => {
    if (temporizador.current) clearTimeout(temporizador.current)
    peticion.current?.abort()
    if (!texto.trim()) {
      setSugerencias([])
      setAbierto(false)
      return
    }
    temporizador.current = setTimeout(() => {
      const actual = new AbortController()
      peticion.current = actual
      listarClientes(texto, 8, actual.signal)
        .then((encontrados) => {
          if (actual.signal.aborted) return
          setSugerencias(encontrados)
          setActiva(-1)
          setAbierto(encontrados.length > 0)
        })
        .catch(() => {
          if (!actual.signal.aborted) setAbierto(false)
        })
    }, ESPERA_MS)
  }

  const elegir = (cliente: ClienteSugerido) => {
    onCambio(cliente.nombre)
    setAbierto(false)
    setSugerencias([])
  }

  const alPulsar = (evento: React.KeyboardEvent<HTMLInputElement>) => {
    if (evento.key === 'Escape') {
      setAbierto(false)
      return
    }
    if (!abierto || sugerencias.length === 0) return
    if (evento.key === 'ArrowDown') {
      evento.preventDefault()
      setActiva((i) => (i + 1) % sugerencias.length)
    } else if (evento.key === 'ArrowUp') {
      evento.preventDefault()
      setActiva((i) => (i <= 0 ? sugerencias.length - 1 : i - 1))
    } else if (evento.key === 'Enter' && activa >= 0) {
      evento.preventDefault()
      elegir(sugerencias[activa])
    }
  }

  const idLista = `${id}-sugerencias`

  return (
    <div className="bm-suggest">
      <input
        id={id}
        autoComplete="off"
        placeholder="Escribir o seleccionar cliente"
        value={valor}
        disabled={deshabilitado}
        role="combobox"
        aria-expanded={abierto}
        aria-controls={idLista}
        aria-autocomplete="list"
        aria-required="true"
        aria-activedescendant={activa >= 0 ? `${id}-opcion-${activa}` : undefined}
        onChange={(e) => {
          onCambio(e.target.value)
          buscar(e.target.value)
        }}
        onKeyDown={alPulsar}
        onBlur={() => setAbierto(false)}
        {...atributosError}
      />
      {abierto && (
        <ul id={idLista} className="bm-suggest-list" role="listbox">
          {sugerencias.map((cliente, i) => (
            <li
              key={cliente.id}
              id={`${id}-opcion-${i}`}
              role="option"
              aria-selected={i === activa}
              data-active={i === activa}
              // mouseDown y no click: el blur del campo cierra la lista antes de que llegue el click.
              onMouseDown={(e) => {
                e.preventDefault()
                elegir(cliente)
              }}
            >
              {cliente.nombre}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
