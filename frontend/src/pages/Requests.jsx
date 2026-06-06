import { useEffect, useState } from 'react'
import Navbar from '../components/layout/Navbar'
import EscalationTimeline from '../components/EscalationTimeline'
import { createRequest, listRequests, triggerMatching } from '../services/api'
import { Plus, Loader2, Play } from 'lucide-react'

const BLOOD_GROUPS = [
  'O Positive', 'O Negative', 'A Positive', 'A Negative',
  'B Positive', 'B Negative', 'AB Positive', 'AB Negative',
]

export default function Requests() {
  const [requests, setRequests] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [form, setForm] = useState({
    patient_id: '', blood_group: 'O Positive', units_needed: 1,
    transfusion_date: '', notes: '',
  })
  const [matchingId, setMatchingId] = useState(null)

  const load = () => {
    setLoading(true)
    listRequests({ limit: 50 }).then(r => setRequests(r.data.requests || [])).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    try {
      await createRequest(form)
      setShowForm(false)
      setForm({ patient_id: '', blood_group: 'O Positive', units_needed: 1, transfusion_date: '', notes: '' })
      load()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to create request')
    } finally {
      setSubmitting(false)
    }
  }

  const startMatching = async (req) => {
    setMatchingId(req.request_id)
    try {
      await triggerMatching({
        request_id: req.request_id,
        patient_id: req.patient_id,
        patient_blood_group: req.blood_group,
        patient_lat: 17.3922792,
        patient_lon: 78.4602749,
        transfusion_date: req.collection_window_end || req.created_at?.slice(0, 10),
      })
      load()
    } finally {
      setMatchingId(null)
    }
  }

  const statusBg = {
    open: 'bg-blue-50 text-blue-700', matching: 'bg-yellow-50 text-yellow-700',
    matched: 'bg-indigo-50 text-indigo-700', fulfilled: 'bg-green-50 text-green-700',
    cancelled: 'bg-slate-100 text-slate-500', escalated: 'bg-orange-50 text-orange-700',
  }

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <Navbar title="Blood Requests" subtitle="Manage and track all blood requests" />
      <div className="flex-1 overflow-y-auto p-6 space-y-5">

        <div className="flex justify-between items-center">
          <p className="text-sm text-slate-500">{requests.length} total requests</p>
          <button
            onClick={() => setShowForm(!showForm)}
            className="flex items-center gap-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium px-4 py-2 rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Request
          </button>
        </div>

        {showForm && (
          <div className="bg-white border border-slate-200 rounded-xl p-5">
            <h3 className="font-semibold text-slate-900 mb-4">Create Blood Request</h3>
            <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Patient ID *</label>
                <input required value={form.patient_id} onChange={e => setForm({ ...form, patient_id: e.target.value })}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-red-400"
                  placeholder="Patient user_id"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Blood Group *</label>
                <select value={form.blood_group} onChange={e => setForm({ ...form, blood_group: e.target.value })}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-red-400"
                >
                  {BLOOD_GROUPS.map(bg => <option key={bg}>{bg}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Units Needed</label>
                <input type="number" min={1} max={10} value={form.units_needed} onChange={e => setForm({ ...form, units_needed: +e.target.value })}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-red-400"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Transfusion Date *</label>
                <input required type="date" value={form.transfusion_date} onChange={e => setForm({ ...form, transfusion_date: e.target.value })}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-red-400"
                />
              </div>
              <div className="md:col-span-2">
                <label className="block text-xs font-medium text-slate-600 mb-1">Notes</label>
                <textarea value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-red-400"
                  rows={2} placeholder="Optional notes..."
                />
              </div>
              <div className="md:col-span-2 flex gap-2 justify-end">
                <button type="button" onClick={() => setShowForm(false)}
                  className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg">Cancel</button>
                <button type="submit" disabled={submitting}
                  className="flex items-center gap-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium px-4 py-2 rounded-lg disabled:opacity-60">
                  {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
                  Create Request
                </button>
              </div>
            </form>
          </div>
        )}

        {loading
          ? <div className="text-center py-10 text-slate-400">Loading requests…</div>
          : (
            <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead className="border-b border-slate-100">
                  <tr>
                    {['Request ID', 'Blood Group', 'Units', 'Urgency', 'Status', 'Window', 'Actions'].map(h => (
                      <th key={h} className="text-left py-3 px-4 text-xs font-semibold text-slate-500 uppercase tracking-wide">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {requests.map(r => (
                    <tr key={r.request_id} className="hover:bg-slate-50">
                      <td className="py-3 px-4 font-mono text-xs text-slate-500">{r.request_id?.slice(0, 8)}…</td>
                      <td className="py-3 px-4">
                        <span className="text-xs font-bold text-red-700 bg-red-50 px-2 py-0.5 rounded">{r.blood_group}</span>
                      </td>
                      <td className="py-3 px-4 text-slate-700">{r.units_needed}</td>
                      <td className="py-3 px-4">
                        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                          r.urgency_level === 'critical' ? 'bg-red-100 text-red-700'
                          : r.urgency_level === 'high' ? 'bg-orange-100 text-orange-700'
                          : 'bg-green-100 text-green-700'
                        }`}>{r.urgency_level}</span>
                      </td>
                      <td className="py-3 px-4">
                        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${statusBg[r.status] || 'bg-slate-100 text-slate-500'}`}>
                          {r.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-xs text-slate-500">
                        {r.collection_window_start} → {r.collection_window_end}
                      </td>
                      <td className="py-3 px-4">
                        {r.status === 'open' && (
                          <button onClick={() => startMatching(r)}
                            disabled={matchingId === r.request_id}
                            className="flex items-center gap-1 text-xs bg-indigo-50 hover:bg-indigo-100 text-indigo-700 px-2.5 py-1 rounded-lg font-medium">
                            {matchingId === r.request_id
                              ? <Loader2 className="w-3 h-3 animate-spin" />
                              : <Play className="w-3 h-3" />}
                            Match
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {requests.length === 0 && (
                <div className="text-center py-10 text-slate-400 text-sm">No requests found</div>
              )}
            </div>
          )
        }
      </div>
    </div>
  )
}
