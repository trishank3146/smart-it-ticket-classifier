import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import TicketForm from './components/TicketForm.jsx'
import TicketList from './components/TicketList.jsx'
import CategoryReport from './components/CategoryReport.jsx'
import StatCards from './components/StatCards.jsx'

const NO_FILTERS = { category: '', status: '', priority: '', search: '', overdue: '' }

export default function App() {
  const [tickets, setTickets] = useState([])
  const [filters, setFilters] = useState(NO_FILTERS)
  const [report, setReport] = useState([])
  const [summary, setSummary] = useState(null)
  const [metrics, setMetrics] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [retraining, setRetraining] = useState(false)

  const refresh = useCallback(async () => {
    try {
      const [ticketData, reportData, summaryData] = await Promise.all([
        api.listTickets(filters),
        api.categoryReport(),
        api.summary(),
      ])
      setTickets(ticketData)
      setReport(reportData)
      setSummary(summaryData)
      setError('')
    } catch (err) {
      setError(`Could not reach the API. Is the Flask backend running? (${err.message})`)
    }
  }, [filters])

  useEffect(() => {
    refresh()
  }, [refresh])

  useEffect(() => {
    api.modelMetrics().then(setMetrics).catch(() => {})
  }, [])

  const handleUpdate = async (id, changes) => {
    try {
      await api.updateTicket(id, changes)
      refresh()
    } catch (err) {
      setError(err.message)
    }
  }

  const handleDelete = async (id) => {
    if (!window.confirm('Delete this ticket?')) return
    await api.deleteTicket(id)
    refresh()
  }

  // Retrain the ML model with the categories agents corrected
  const handleRetrain = async () => {
    setRetraining(true)
    try {
      const result = await api.retrainModel()
      setNotice(`${result.message}. Test accuracy: ${(result.accuracy * 100).toFixed(1)}%`)
      setMetrics(await api.modelMetrics())
    } catch (err) {
      setError(err.message)
    } finally {
      setRetraining(false)
    }
  }

  const corrections = summary?.manually_corrected || 0

  return (
    <div className="app">
      <header className="header">
        <div>
          <h1>Smart IT Support Ticket Classifier</h1>
          <p>Tickets are automatically categorised, prioritised and routed to the right team.</p>
        </div>
        {metrics && (
          <div className="model-badge">
            <div>
              Model accuracy <strong>{(metrics.accuracy * 100).toFixed(1)}%</strong>
            </div>
            <button className="small-btn" onClick={handleRetrain}
                    disabled={retraining || corrections === 0}
                    title="Adds tickets that agents re-categorised to the training data">
              {retraining ? 'Retraining…' : `Retrain with ${corrections} correction(s)`}
            </button>
          </div>
        )}
      </header>

      {error && <div className="alert">{error}</div>}
      {notice && <div className="notice" onClick={() => setNotice('')}>{notice}</div>}

      <StatCards summary={summary} />

      <div className="layout">
        <TicketForm onCreated={refresh} />
        <CategoryReport rows={report} />
      </div>

      <TicketList
        tickets={tickets}
        filters={filters}
        onFilterChange={setFilters}
        onUpdate={handleUpdate}
        onDelete={handleDelete}
      />

      <footer className="footer">
        Built by Segu Gopi Trishank · React.js · Flask · MySQL · scikit-learn
      </footer>
    </div>
  )
}
