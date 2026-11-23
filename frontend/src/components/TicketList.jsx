import { Fragment, useState } from 'react'
import { CATEGORIES, PRIORITIES, STATUSES } from '../api'
import TicketDetails, { formatTime } from './TicketDetails.jsx'

export default function TicketList({ tickets, filters, onFilterChange, onUpdate, onDelete }) {
  const [openId, setOpenId] = useState(null)
  const setFilter = (name, value) => onFilterChange({ ...filters, [name]: value })

  return (
    <section className="card">
      <div className="list-header">
        <h2>Tickets ({tickets.length})</h2>
        <div className="filters">
          <input placeholder="Search…" value={filters.search}
                 onChange={(e) => setFilter('search', e.target.value)} />
          <select value={filters.category} onChange={(e) => setFilter('category', e.target.value)}>
            <option value="">All categories</option>
            {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
          </select>
          <select value={filters.priority} onChange={(e) => setFilter('priority', e.target.value)}>
            <option value="">All priorities</option>
            {PRIORITIES.map((p) => <option key={p}>{p}</option>)}
          </select>
          <select value={filters.status} onChange={(e) => setFilter('status', e.target.value)}>
            <option value="">All statuses</option>
            {STATUSES.map((s) => <option key={s}>{s}</option>)}
          </select>
          <label className="checkbox">
            <input type="checkbox" checked={filters.overdue === 'true'}
                   onChange={(e) => setFilter('overdue', e.target.checked ? 'true' : '')} />
            Overdue only
          </label>
        </div>
      </div>

      {tickets.length === 0 ? (
        <p className="muted">No tickets match. Raise one above or clear the filters.</p>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>#</th>
                <th>Ticket</th>
                <th>Category</th>
                <th>Priority</th>
                <th>Team</th>
                <th>Due</th>
                <th>Status</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {tickets.map((t) => (
                <Fragment key={t.id}>
                  <tr className={t.is_overdue ? 'row-overdue' : ''}>
                    <td>{t.id}</td>
                    <td>
                      <button className="link-title" onClick={() => setOpenId(openId === t.id ? null : t.id)}>
                        {openId === t.id ? '▾' : '▸'} {t.title}
                      </button>
                      <div className="muted small">{t.requester_email}</div>
                    </td>
                    <td>
                      {/* Agents can correct the model's prediction */}
                      <select value={t.category}
                              onChange={(e) => onUpdate(t.id, { category: e.target.value })}>
                        {CATEGORIES.map((c) => <option key={c}>{c}</option>)}
                      </select>
                      <div className="muted small">
                        {t.manually_corrected ? 'corrected by agent'
                          : `${(t.confidence * 100).toFixed(0)}% confidence`}
                      </div>
                    </td>
                    <td>
                      <select className={`pri-${t.priority.toLowerCase()}`} value={t.priority}
                              onChange={(e) => onUpdate(t.id, { priority: e.target.value })}>
                        {PRIORITIES.map((p) => <option key={p}>{p}</option>)}
                      </select>
                    </td>
                    <td className="small">{t.assigned_team}</td>
                    <td className="small">
                      {formatTime(t.due_at)}
                      {t.is_overdue && <div><span className="tag overdue">Overdue</span></div>}
                    </td>
                    <td>
                      <select value={t.status}
                              onChange={(e) => onUpdate(t.id, { status: e.target.value })}>
                        {STATUSES.map((s) => <option key={s}>{s}</option>)}
                      </select>
                    </td>
                    <td>
                      <button className="link" onClick={() => onDelete(t.id)}>Delete</button>
                    </td>
                  </tr>
                  {openId === t.id && (
                    <tr className="details-row">
                      <td colSpan={8}><TicketDetails ticket={t} /></td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
