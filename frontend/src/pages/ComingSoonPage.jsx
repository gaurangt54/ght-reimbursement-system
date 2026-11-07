export function ComingSoonPage({ title, phase }) {
    return (
      <div className="card empty">
        <h1>{title}</h1>
        <p className="muted">This screen is built in Phase {phase}.</p>
      </div>
    )
  }