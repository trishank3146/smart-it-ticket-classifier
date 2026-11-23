import { useEffect, useState } from 'react'
import { api } from '../api'

const EMPTY = { title: '', description: '', requester_email: '' }

export default function TicketForm({ onCreated }) {
  const [form, setForm] = useState(EMPTY)
  const [preview, setPreview] = useState(null)
  const [message, setMessage] = useState('')
  const [submitting, setSubmitting] = useState(false)

  // Live prediction: classify the text 500 ms after the user stops typing
  useEffect(() => {
    const text = `${form.title} ${form.description}`.trim()
    if (text.length < 10) {
      setPreview(null)
      return
    }
    const timer = setTimeout(() => {
      api.classify(text).then(setPreview).catch(() => setPreview(null))
    }, 500)
    return () => clearTimeout(timer)
  }, [form.title, form.description])

  const handleChange = (e) => setForm({ ...form, [e.target.name]: e.target.value })

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    setMessage('')
    try {
      const ticket = await api.createTicket(form)
      setMessage(`Ticket #${ticket.id} created → ${ticket.category} (${ticket.assigned_team})`)
      setForm(EMPTY)
      setPreview(null)
      onCreated()
    } catch (err) {
      setMessage(`Error: ${err.message}`)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <section className="card">
      <h2>Raise a ticket</h2>
      <form onSubmit={handleSubmit} className="form">
        <label>
          Title
          <input name="title" value={form.title} onChange={handleChange}
                 placeholder="e.g. VPN keeps disconnecting" maxLength={200} required />
        </label>
        <label>
          Description
          <textarea name="description" value={form.description} onChange={handleChange}
                    rows={4} placeholder="Describe the issue" required />
        </label>
        <label>
          Your email
          <input name="requester_email" type="email" value={form.requester_email}
                 onChange={handleChange} placeholder="name@company.com" required />
        </label>

        {preview && (
          <div className="preview">
            <span>Predicted:</span>
            <span className={`tag cat-${preview.category.toLowerCase()}`}>{preview.category}</span>
            <span className={`tag pri-${preview.priority.toLowerCase()}`}>{preview.priority}</span>
            <span className="muted">
              {(preview.confidence * 100).toFixed(0)}% confident · {preview.assigned_team}
            </span>
          </div>
        )}

        <button type="submit" disabled={submitting}>
          {submitting ? 'Submitting…' : 'Submit ticket'}
        </button>
        {message && <p className="message">{message}</p>}
      </form>
    </section>
  )
}
