/** Progreso del análisis mientras el worker procesa (HU-22, RNF25). */
export default function BarraProgreso({ etapa, progreso }: { etapa: string; progreso: number }) {
  return (
    <div className="bm-card" role="status" aria-live="polite">
      <div className="bm-row-between" style={{ marginBottom: 10 }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>{etapa}</span>
        <span style={{ fontSize: 12, color: 'var(--muted)' }}>{progreso}%</span>
      </div>
      <div className="bm-progress">
        <div className="bm-progress-fill" style={{ width: `${progreso}%` }} />
      </div>
      <p style={{ fontSize: 12, color: 'var(--muted)', margin: '10px 0 0' }}>
        El análisis puede tardar hasta dos minutos. Puedes dejar esta pantalla abierta.
      </p>
    </div>
  )
}
