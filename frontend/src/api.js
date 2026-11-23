// Small wrapper around fetch for the Flask REST API.
const BASE = '/api'

async function request(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (res.status === 204) return null
  const data = await res.json()
  if (!res.ok) throw new Error(data.error || `Request failed (${res.status})`)
  return data
}

export const api = {
  classify: (text) => request('/classify', { method: 'POST', body: JSON.stringify({ text }) }),
  createTicket: (ticket) => request('/tickets', { method: 'POST', body: JSON.stringify(ticket) }),
  listTickets: (filters = {}) => {
    const params = new URLSearchParams(
      Object.entries(filters).filter(([, value]) => value)
    ).toString()
    return request(`/tickets${params ? `?${params}` : ''}`)
  },
  updateTicket: (id, changes) =>
    request(`/tickets/${id}`, { method: 'PATCH', body: JSON.stringify(changes) }),
  deleteTicket: (id) => request(`/tickets/${id}`, { method: 'DELETE' }),
  ticketHistory: (id) => request(`/tickets/${id}/history`),
  categoryReport: () => request('/reports/categories'),
  summary: () => request('/reports/summary'),
  modelMetrics: () => request('/model/metrics'),
  retrainModel: () => request('/model/retrain', { method: 'POST' }),
}

export const CATEGORIES = [
  'Hardware', 'Software', 'Network', 'Access', 'Email', 'Printer', 'Security', 'Database',
]
export const STATUSES = ['Open', 'In Progress', 'Resolved', 'Closed']
export const PRIORITIES = ['Critical', 'High', 'Medium', 'Low']
