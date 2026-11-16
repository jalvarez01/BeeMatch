import { useEffect, useState } from 'react'

import { listarClientes } from '../api/clientes'
import type { ClienteSugerido } from '../types'

const MAXIMO = 100

interface Props {
  id: string
  valor: string
  onCambio: (valor: string) => void
  deshabilitado?: boolean
  atributosError?: Pick<React.InputHTMLAttributes<HTMLInputElement>, 'aria-invalid' | 'aria-describedby'>
}

/**
 * HU-12: selector de cliente. Los clientes los registra la superadministradora y el
 * resto de las personas elige uno de la lista; no se escribe uno nuevo. Si la solicitud
 * ya tenía un cliente que dejó de estar en la lista, se conserva como opción para no
 * perderlo al editarla.
 */
export default function CampoCliente({ id, valor, onCambio, deshabilitado, atributosError }: Props) {
  const [clientes, setClientes] = useState<ClienteSugerido[]>([])
  const [cargado, setCargado] = useState(false)
  const [fallo, setFallo] = useState(false)

  useEffect(() => {
    const peticion = new AbortController()
    listarClientes('', MAXIMO, peticion.signal)
      .then((encontrados) => {
        if (peticion.signal.aborted) return
        setClientes(encontrados)
        setCargado(true)
      })
      .catch(() => {
        if (!peticion.signal.aborted) {
          setFallo(true)
          setCargado(true)
        }
      })
    return () => peticion.abort()
  }, [])

  const enLista = clientes.some((c) => c.nombre.toLowerCase() === valor.trim().toLowerCase())
  const sinClientes = cargado && !fallo && clientes.length === 0

  return (
    <>
      <select
        id={id}
        value={valor}
        disabled={deshabilitado || !cargado}
        aria-required="true"
        onChange={(e) => onCambio(e.target.value)}
        {...atributosError}
      >
        <option value="">{cargado ? 'Selecciona un cliente' : 'Cargando clientes…'}</option>
        {valor.trim() && !enLista && <option value={valor}>{valor}</option>}
        {clientes.map((cliente) => (
          <option key={cliente.id} value={cliente.nombre}>
            {cliente.nombre}
          </option>
        ))}
      </select>
      {sinClientes && (
        <p style={{ fontSize: 12, color: 'var(--muted)', margin: '6px 0 0' }}>
          Aún no hay clientes registrados. Pídele a la superadministradora que los registre.
        </p>
      )}
      {fallo && (
        <p style={{ fontSize: 12, color: 'var(--muted)', margin: '6px 0 0' }}>
          No se pudo cargar la lista de clientes. Recarga la página.
        </p>
      )}
    </>
  )
}
