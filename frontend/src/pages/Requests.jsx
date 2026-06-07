import { useEffect, useState } from 'react'
import Navbar from '../components/layout/Navbar'
import EscalationTimeline from '../components/EscalationTimeline'
import { createRequest, listRequests, triggerMatching, updateRequest, issueBloodUnits, releaseBloodUnits } from '../services/api'
import { Plus, Loader2, Play, X, CheckCircle, RefreshCw, ChevronDown, ChevronUp, User, MapPin } from 'lucide-react'

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
    transfusion_date: '', notes: '', patient_lat: '', patient_lon: '',
  })
  const [matchingId, setMatchingId] = useState(null)
  const [matchResult, setMatchResult] = useState({})
  const [expandedMatch, setExpandedMatch] = useState(null)
  const [actionLoading, setActionLoading] = useState(null)
  const [toast, setToast] = useState(null)

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 4000)
  }

  const load = () => {
    setLoading(true)
    listRequests({ limit: 100 }).then(r => setRequests(r.data.requests || [])).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    try {
      await createRequest({
        patient_id: form.patient_id,
        blood_group: form.blood_group,
        units_needed: form.units_needed,
        transfusion_date: form.transfusion_date,
        notes: form.notes,
        patient_lat: parseFloat(form.patient_lat) || 17.3922792,
        patient_lon: parseFloat(form.patient_lon) || 78.4602749,
      })
      setShowForm(false)
      setForm({ patient_id: '', blood_group: 'O Positive', units_needed: 1, transfusion_date: '', notes: '', patient_lat: '', patient_lon: '' })
      load()
      showToast('Blood request created successfully')
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to create request')
    } finally {
      setSubmitting(false)
    }
  }

  const startMatching = async (req) => {
    setMatchingId(req.request_id)
    try {
      const res = await triggerMatching({
        request_id: req.request_id,
        patient_id: req.patient_id,
        patient_blood_group: req.blood_group,
        patient_lat: parseFloat(req.patient_lat) || 17.3922792,
        patient_lon: parseFloat(req.patient_lon) || 78.4602749,
        transfusion_date: req.transfusion_date || req.collection_window_end || req.created_at?.slice(0, 10),
      })
      const ranked = res.data.ranked_donors || []
      const notifsSent = res.data.notifications_sent?.filter(n => n.success).length || 0
      setMatchResult({ ...matchResult, [req.request_id]: { ranked, notifsSent } })
      showToast(`Matched ${ranked.length} donors. ${notifsSent} notification${notifsSent !== 1 ? 's' : ''} sent.`)
      load()
    } catch (err) {
      showToast(err.response?.data?.detail || 'Matching failed', 'error')
    } finally {
      setMatchingId(null)
    }
  }

  const cancelRequest = async (reqId) => {
    if (!window.confirm('Cancel this blood request?')) return
    setActionLoading(`cancel-${reqId}`)
    try {
      await updateRequest(reqId, { status: 'cancelled' })
      load()
      showToast('Request cancelled')
    } catch (err) {
      showToast(err.response?.data?.detail || 'Cancel failed', 'error')
    } finally {
      setActionLoading(null)
    }
  }

  const issueRequest = async (reqId) => {
    setActionLoading(`issue-${reqId}`)
    try {
      const r = await issueBloodUnits(reqId)
      showToast(`${r.data.units_issued} unit(s) issued. Transfusion complete!`)
      load()
    } catch (err) {
      showToast(err.response?.data?.detail || 'Issue failed', 'error')
    } finally {
      setActionLoading(null)
    }
  }

  const releaseRequest = async (reqId) => {
    if (!window.confirm('Release reserved units back to stock?')) return
    setActionLoading(`release-${reqId}`)
    try {
      const r = await releaseBloodUnits(reqId)
      showToast(`${r.data.units_released} unit(s) released back to inventory`)
      load()
    } catch (err) {
      showToast(err.response?.data?.detail || 'Release failed', 'error')
    } finally {
      setActionLoading(null)
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

        {/* Toast */}
        {toast && (
          <div className={`text-sm px-4 py-3 rounded-lg ${
            toast.type === 'error' ? 'bg-red-50 text-red-700 border border-red-200'
            : 'bg-green-50 text-green-700 border border-green-200'
          }`}>
            {toast.msg}
          </div>
        )}

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
                  placeholder="Patient user_id" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Blood Group *</label>
                <select value={form.blood_group} onChange={e => setForm({ ...form, blood_group: e.target.value })}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-red-400">
                  {BLOOD_GROUPS.map(bg => <option key={bg}>{bg}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Units Needed</label>
                <input type="number" min={1} max={10} value={form.units_needed} onChange={e => setForm({ ...form, units_needed: +e.target.value })}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Transfusion Date *</label>
                <input required type="date" value={form.transfusion_date} onChange={e => setForm({ ...form, transfusion_date: e.target.value })}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-red-400"
                  min={new Date().toISOString().slice(0, 10)} />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Patient Latitude</label>
                <input type="number" step="any" value={form.patient_lat} onChange={e => setForm({ ...form, patient_lat: e.target.value })}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-red-400"
                  placeholder="17.3922792 (default: Hyderabad)" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Patient Longitude</label>
                <input type="number" step="any" value={form.patient_lon} onChange={e => setForm({ ...form, patient_lon: e.target.value })}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-red-400"
                  placeholder="78.4602749 (default: Hyderabad)" />
              </div>
              <div className="md:col-span-2">
                <label className="block text-xs font-medium text-slate-600 mb-1">Notes</label>
                <textarea value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-red-400"
                  rows={2} placeholder="Optional notes (condition, hospital, etc.)" />
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
                <tbody>
                  {requests.map(r => (
                    <>
                    <tr key={r.request_id} className="hover:bg-slate-50 border-b border-slate-50">
                      <td className="py-3 px-4">
                        <span className="font-mono text-xs text-slate-500">{r.request_id?.slice(0, 8)}…</span>
                        {matchResult[r.request_id] && (
                          <button
                            onClick={() => setExpandedMatch(expandedMatch === r.request_id ? null : r.request_id)}
                            className="flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-700 mt-0.5 font-medium"
                          >
                            {matchResult[r.request_id].ranked.filter(d => d.user_id !== 'NGO_ESCALATION').length} donor{matchResult[r.request_id].ranked.filter(d => d.user_id !== 'NGO_ESCALATION').length !== 1 ? 's' : ''} matched
                            {expandedMatch === r.request_id ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                          </button>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        <span className="text-xs font-bold text-red-700 bg-red-50 px-2 py-0.5 rounded">{r.blood_group}</span>
                      </td>
                      <td className="py-3 px-4 text-slate-700">{r.units_needed}</td>
                      <td className="py-3 px-4">
                        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                          r.urgency_level === 'critical' ? 'bg-red-100 text-red-700'
                          : r.urgency_level === 'high' ? 'bg-orange-100 text-orange-700'
                          : 'bg-green-100 text-green-700'
                        }`}>{r.urgency_level || '—'}</span>
                      </td>
                      <td className="py-3 px-4">
                        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${statusBg[r.status] || 'bg-slate-100 text-slate-500'}`}>
                          {r.status}
                        </span>
                      </td>
                      <td className="py-3 px-4 text-xs text-slate-500 max-w-32">
                        <div>{r.collection_window_start}</div>
                        <div className="text-slate-400">→ {r.collection_window_end}</div>
                      </td>
                      <td className="py-3 px-4">
                        <div className="flex flex-wrap gap-1.5">
                          {['open', 'matching'].includes(r.status) && (
                            <button onClick={() => startMatching(r)}
                              disabled={matchingId === r.request_id}
                              className="flex items-center gap-1 text-xs bg-indigo-50 hover:bg-indigo-100 text-indigo-700 px-2 py-1 rounded-lg font-medium">
                              {matchingId === r.request_id ? <Loader2 className="w-3 h-3 animate-spin" /> : <Play className="w-3 h-3" />}
                              {r.status === 'matching' ? 'Re-match' : 'Match'}
                            </button>
                          )}
                          {r.status === 'matched' && (
                            <>
                              <button onClick={() => issueRequest(r.request_id)}
                                disabled={!!actionLoading}
                                className="flex items-center gap-1 text-xs bg-green-600 hover:bg-green-700 text-white px-2 py-1 rounded-lg font-medium">
                                {actionLoading === `issue-${r.request_id}` ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle className="w-3 h-3" />}
                                Issue
                              </button>
                              <button onClick={() => releaseRequest(r.request_id)}
                                disabled={!!actionLoading}
                                className="flex items-center gap-1 text-xs bg-slate-100 hover:bg-slate-200 text-slate-600 px-2 py-1 rounded-lg font-medium">
                                {actionLoading === `release-${r.request_id}` ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                                Release
                              </button>
                            </>
                          )}
                          {['open', 'matching', 'matched'].includes(r.status) && (
                            <button onClick={() => cancelRequest(r.request_id)}
                              disabled={!!actionLoading}
                              className="flex items-center gap-1 text-xs bg-red-50 hover:bg-red-100 text-red-600 px-2 py-1 rounded-lg font-medium">
                              {actionLoading === `cancel-${r.request_id}` ? <Loader2 className="w-3 h-3 animate-spin" /> : <X className="w-3 h-3" />}
                              Cancel
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                    {/* Expandable matched donor list */}
                    {expandedMatch === r.request_id && matchResult[r.request_id] && (
                      <tr key={`${r.request_id}-donors`}>
                        <td colSpan={7} className="px-4 pb-4 bg-indigo-50">
                          <div className="rounded-xl border border-indigo-100 bg-white p-4">
                            <p className="text-xs font-semibold text-indigo-700 mb-3 uppercase tracking-wide">
                              Donors Contacted for This Request
                            </p>
                            {matchResult[r.request_id].ranked.filter(d => d.user_id !== 'NGO_ESCALATION').length === 0 ? (
                              <p className="text-sm text-slate-400">No eligible donors found. Try Re-match after new donors register.</p>
                            ) : (
                              <div className="space-y-2">
                                {matchResult[r.request_id].ranked
                                  .filter(d => d.user_id !== 'NGO_ESCALATION')
                                  .map((d, i) => (
                                    <div key={d.user_id} className="flex items-center gap-4 text-sm py-2 border-b border-slate-50 last:border-0">
                                      <span className="text-xs font-bold text-indigo-600 w-5">#{i + 1}</span>
                                      <div className="flex items-center gap-1.5 min-w-36">
                                        <User className="w-3.5 h-3.5 text-slate-400" />
                                        <span className="font-medium text-slate-800">{d.name || d.user_id?.slice(0, 8)}</span>
                                      </div>
                                      <span className="text-xs font-bold text-red-700 bg-red-50 px-2 py-0.5 rounded">{d.blood_group}</span>
                                      <div className="flex items-center gap-1 text-xs text-slate-500">
                                        <MapPin className="w-3 h-3" />
                                        {d.distance_km === 0 ? 'Same area' : d.distance_km != null ? `${d.distance_km} km` : 'Unknown'}
                                      </div>
                                      <span className="text-xs text-slate-500">Score: <strong className="text-slate-700">{d.donor_score}</strong></span>
                                      <span className="text-xs text-slate-400">{d.role || 'Donor'}</span>
                                      {d.phone_number && (
                                        <span className="text-xs text-slate-500 ml-auto">{d.phone_number}</span>
                                      )}
                                    </div>
                                  ))}
                              </div>
                            )}
                            {matchResult[r.request_id].notifsSent > 0 && (
                              <p className="text-xs text-green-600 mt-3">
                                ✓ {matchResult[r.request_id].notifsSent} notification{matchResult[r.request_id].notifsSent !== 1 ? 's' : ''} sent via email/SMS
                              </p>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                    </>
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
