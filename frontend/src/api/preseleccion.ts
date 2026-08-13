import { BASE_URL, leerSesion } from './client'

/** Descarga el archivo de preselección (HU-25). */
export async function exportarPreseleccion(
  busquedaId: string,
  formato: 'PDF' | 'XLSX' = 'XLSX',
): Promise<void> {
  const sesion = leerSesion<{ access_token?: string }>()

  const respuesta = await fetch(`${BASE_URL}/preseleccion/${busquedaId}/exportar`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${sesion?.access_token ?? ''}`,
    },
    body: JSON.stringify({ formato }),
  })

  if (!respuesta.ok) {
    const cuerpo = await respuesta.json().catch(() => ({}))
    throw new Error(cuerpo.detail || 'No fue posible exportar la preselección.')
  }

  const blob = await respuesta.blob()
  const url = URL.createObjectURL(blob)
  const enlace = document.createElement('a')
  enlace.href = url
  enlace.download = `preseleccion.${formato.toLowerCase()}`
  enlace.click()
  URL.revokeObjectURL(url)
}
