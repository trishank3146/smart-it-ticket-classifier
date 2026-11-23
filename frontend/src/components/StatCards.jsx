export default function StatCards({ summary }) {
  if (!summary) return null
  const open = (summary.by_status['Open'] || 0) + (summary.by_status['In Progress'] || 0)
  const urgent = (summary.by_priority['Critical'] || 0) + (summary.by_priority['High'] || 0)
  const sla = summary.sla_compliance_pct

  const cards = [
    { label: 'Total tickets', value: summary.total_tickets },
    { label: 'Open / in progress', value: open },
    { label: 'High + critical', value: urgent },
    { label: 'Overdue (SLA breached)', value: summary.overdue, warn: summary.overdue > 0 },
    { label: 'Resolved within SLA', value: sla === null ? '–' : `${sla}%` },
    { label: 'Corrected by agents', value: summary.manually_corrected },
  ]

  return (
    <div className="stats">
      {cards.map((c) => (
        <div className={`stat${c.warn ? ' stat-warn' : ''}`} key={c.label}>
          <span className="stat-value">{c.value}</span>
          <span className="stat-label">{c.label}</span>
        </div>
      ))}
    </div>
  )
}
