export default function EstadoVacio({
  titulo,
  texto,
  accion,
}: {
  titulo: string
  texto: string
  accion?: React.ReactNode
}) {
  return (
    <div className="bm-card">
      <div className="bm-empty">
        <h3>{titulo}</h3>
        <p>{texto}</p>
        {accion}
      </div>
    </div>
  )
}
