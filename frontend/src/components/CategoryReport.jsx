// Category-based report: a simple bar chart built with plain CSS.
export default function CategoryReport({ rows }) {
  const max = Math.max(1, ...rows.map((r) => r.total_tickets))

  return (
    <section className="card">
      <h2>Tickets by category</h2>
      {rows.length === 0 ? (
        <p className="muted">The report fills in as tickets are raised.</p>
      ) : (
        <div className="bars">
          {rows.map((r) => (
            <div className="bar-row" key={r.category}>
              <span className="bar-label">{r.category}</span>
              <div className="bar-track">
                <div className={`bar-fill cat-${r.category.toLowerCase()}`}
                     style={{ width: `${(r.total_tickets / max) * 100}%` }} />
              </div>
              <span className="bar-value">
                {r.total_tickets}
                <span className="muted small"> · {r.open_tickets} open</span>
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  )
}
