import { useEffect, useState } from 'react'
import { api } from '../api'

const ACTION_LABELS = {
  created: 'Ticket created',
  status_changed: 'Status changed',
  priority_changed: 'Priority changed',
  category_corrected: 'Category corrected by agent',
}

export function formatTime(iso) {
  return iso ? new Date(iso).toLocaleString() : '–'
}

// Expanded row: full description, SLA times and the audit history
export default function TicketDetails({ ticket }) {
  const [history, setHistory] = useState([])

  useEffect(() => {
    api.ticketHistory(ticket.id).then(setHistory).catch(() => setHistory([]))
  }, [ticket.id, ticket.status, ticket.priority, ticket.category])

  return (
    <div className="details">
      <div>
        <h4>Description</h4>
        <p>{ticket.description}</p>
        <h4>SLA</h4>
        <p className="small">
          Created {formatTime(ticket.created_at)}<br />
          Due {formatTime(ticket.due_at)}
          {ticket.resolved_at && <><br />Resolved {formatTime(ticket.resolved_at)}</>}
        </p>
      </div>
      <div>
        <h4>History</h4>
        <ul className="timeline">
          {history.map((h) => (
            <li key={h.id}>
              <strong>{ACTION_LABELS[h.action] || h.action}</strong>
              {h.new_value && `: ${h.old_value ? `${h.old_value} → ` : ''}${h.new_value}`}
              <div className="muted small">{formatTime(h.changed_at)}</div>
            </li>
          ))}
        </ul>
      </div>
    </div>
  )
}
