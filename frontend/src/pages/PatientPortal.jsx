/**
 * Patient Portal — shown to users with system_role = "patient"
 *
 * Features:
 * - Submit blood requests
 * - Track status of existing requests (with escalation timeline)
 * - View assigned donors / blood units
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { createRequest, listRequests, updateRequest, triggerMatching, getMe } from '../services/api'
import { Activity, Plus, Droplets, LogOut, Loader2, CheckCircle, RefreshCw, X } from 'lucide-react'
import EscalationTimeline from '../components/EscalationTimeline'

const statusColors = {
  open: 'bg-blue-50 text-blue-700',
  matching: 'bg-yellow-50 text-yellow-700',
  matched: 'bg-indigo-50 text-indigo-700',
  fulfilled: 'bg-green-50 text-green-700',
  cancelled: 'bg-slate-100 text-slate-500',
  escalated: 'bg-orange-50 text-orange-700',
}

const urgencyColors = {
  critical: 'bg-red-100 text-red-700',
  high: 'bg-orange-100 text-orange-700',
  standard: 'bg-green-100 text-green-700',
}

export default function PatientPortal() {
  const { user, logout } = useAuth()
  const nav = useNavigate()
  const [requests, setRequests] = useState([])
  const [loading, setLoading] = useState(true)
  const [showForm, setShowForm] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [cancelling, setCancelling] = useState(null)
  const [rematching, setRematching] = useState(null)
  const [profile, setProfile] = useState(null)   // full profile with lat/lon

  const patientBloodGroup = profile?.blood_group || user?.blood_group || 'O Positive'

  const [form, setForm] = useState({
    units_needed: 1, transfusion_date: '', notes: ''
  })

  useEffect(() => {
    if (!user) { nav('/login'); return }
    // Load full profile so we have lat/lon
    getMe().then(res => setProfile(res.data)).catch(() => {})
    load()
  }, [user])

  const load = async () => {
    setLoading(true)
    try {
      const res = await listRequests({ patient_id: user.user_id, limit: 50 })
      setRequests(res.data.requests || [])
    } finally {
      setLoading(false)
    }
  }

  const getCoords = () => {
    const lat = parseFloat(profile?.latitude ?? user?.latitude)
    const lon = parseFloat(profile?.longitude ?? user?.longitude)
    return {
      patLat: isNaN(lat) ? 17.3850 : lat,
      patLon: isNaN(lon) ? 78.4867 : lon,
    }
  }

  const submit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    try {
      const { patLat, patLon } = getCoords()

      const res = await createRequest({
        ...form,
        blood_group: patientBloodGroup,
        patient_id: user.user_id,
        patient_lat: patLat,
        patient_lon: patLon,
      })
      const newReq = res.data

      setShowForm(false)
      setForm({ units_needed: 1, transfusion_date: '', notes: '' })

      // Auto-trigger matching
      try {
        await triggerMatching({
          request_id: newReq.request_id,
          patient_id: user.user_id,
          patient_blood_group: newReq.blood_group,
          patient_lat: patLat,
          patient_lon: patLon,
          transfusion_date: form.transfusion_date,
        })
      } catch {
        // Non-fatal
      }

      load()
    } catch (err) {
      alert(err.response?.data?.detail || 'Failed to create request')
    } finally {
      setSubmitting(false)
    }
  }

  const rematch = async (req) => {
    setRematching(req.request_id)
    try {
      const { patLat, patLon } = getCoords()
      await triggerMatching({
        request_id: req.request_id,
        patient_id: user.user_id,
        patient_blood_group: req.blood_group,
        patient_lat: patLat,
        patient_lon: patLon,
        transfusion_date: req.transfusion_date || new Date().toISOString().slice(0, 10),
      })
      load()
    } catch (err) {
      alert(err.response?.data?.detail || 'Re-match failed')
    } finally {
      setRematching(null)
    }
  }

  const cancelRequest = async (reqId) => {
    if (!window.confirm('Cancel this blood request?')) return
    setCancelling(reqId)
    try {
      await updateRequest(reqId, { status: 'cancelled' })
      load()
    } finally {
      setCancelling(null)
    }
  }

  const handleLogout = () => { logout(); nav('/login') }

  const open = requests.filter(r => ['open', 'matching'].includes(r.status)).length
  const matched = requests.filter(r => r.status === 'matched').length
  const fulfilled = requests.filter(r => r.status === 'fulfilled').length

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-red-600 flex items-center justify-center">
            <Activity className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="font-bold text-slate-900 text-sm">BloodBridge AI</h1>
            <p className="text-xs text-slate-500">Patient Portal</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <p className="text-sm font-medium text-slate-800">{user?.name}</p>
            <p className="text-xs text-slate-500">{user?.blood_group}</p>
          </div>
          <button onClick={handleLogout} className="p-2 rounded-lg hover:bg-slate-100 text-slate-500">
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </header>

      <div className="max-w-3xl mx-auto p-6 space-y-6">
        {/* Stats */}
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: 'Active Requests', value: open, color: 'text-blue-700' },
            { label: 'Matched', value: matched, color: 'text-indigo-700' },
            { label: 'Fulfilled', value: fulfilled, color: 'text-green-700' },
          ].map(s => (
            <div key={s.label} className="bg-white rounded-xl border border-slate-200 p-4 text-center">
              <p className="text-xs text-slate-500">{s.label}</p>
              <p className={`text-2xl font-bold mt-1 ${s.color}`}>{s.value}</p>
            </div>
          ))}
        </div>

        {/* New request button */}
        <div className="flex justify-between items-center">
          <h2 className="font-semibold text-slate-900">My Blood Requests</h2>
          <button
            onClick={() => setShowForm(!showForm)}
            className="flex items-center gap-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium px-4 py-2 rounded-lg"
          >
            <Plus className="w-4 h-4" />
            New Request
          </button>
        </div>

        {/* New request form */}
        {showForm && (
          <div className="bg-white border border-slate-200 rounded-xl p-5">
            <h3 className="font-semibold text-slate-900 mb-4">New Blood Request</h3>
            <form onSubmit={submit} className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Blood Group</label>
                <div className="w-full border border-slate-200 bg-slate-50 rounded-lg px-3 py-2 text-sm text-slate-700 flex items-center gap-2">
                  <span className="text-red-600 font-semibold">{patientBloodGroup}</span>
                  <span className="text-xs text-slate-400">(your registered blood group)</span>
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Units Needed</label>
                <input type="number" min={1} max={10} value={form.units_needed}
                  onChange={e => setForm({ ...form, units_needed: +e.target.value })}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-red-400" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Transfusion Date *</label>
                <input required type="date" value={form.transfusion_date}
                  onChange={e => setForm({ ...form, transfusion_date: e.target.value })}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-red-400"
                  min={new Date().toISOString().slice(0, 10)} />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Notes</label>
                <input value={form.notes} onChange={e => setForm({ ...form, notes: e.target.value })}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-red-400"
                  placeholder="e.g. thalassemia, surgery" />
              </div>
              <div className="md:col-span-2 flex gap-2 justify-end">
                <button type="button" onClick={() => setShowForm(false)}
                  className="px-4 py-2 text-sm text-slate-600 hover:bg-slate-100 rounded-lg">Cancel</button>
                <button type="submit" disabled={submitting}
                  className="flex items-center gap-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium px-4 py-2 rounded-lg disabled:opacity-60">
                  {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
                  Submit Request
                </button>
              </div>
            </form>
          </div>
        )}

        {/* Requests list */}
        {loading ? (
          <div className="text-center py-12 text-slate-400">Loading requests…</div>
        ) : requests.length === 0 ? (
          <div className="bg-white rounded-xl border border-slate-200 p-10 text-center">
            <Droplets className="w-10 h-10 text-slate-300 mx-auto mb-3" />
            <p className="text-slate-500 text-sm">No blood requests yet.</p>
            <p className="text-slate-400 text-xs mt-1">Click "New Request" to submit your first request.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {requests.map(r => (
              <div key={r.request_id} className="bg-white border border-slate-200 rounded-xl p-5">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1">
                    <div className="flex items-center gap-2 mb-2">
                      <span className="text-sm font-bold text-red-700 bg-red-50 px-2 py-0.5 rounded border border-red-100">
                        {r.blood_group}
                      </span>
                      <span className="text-sm text-slate-700">{r.units_needed} unit{r.units_needed > 1 ? 's' : ''}</span>
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${urgencyColors[r.urgency_level] || 'bg-slate-100 text-slate-500'}`}>
                        {r.urgency_level}
                      </span>
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${statusColors[r.status] || 'bg-slate-100 text-slate-500'}`}>
                        {r.status}
                      </span>
                    </div>
                    <EscalationTimeline status={r.status} urgency={r.urgency_level} createdAt={r.created_at} />
                    <div className="mt-2 text-xs text-slate-400 space-y-0.5">
                      <p>Transfusion: {r.transfusion_date || '—'}</p>
                      <p>Collection window: {r.collection_window_start} → {r.collection_window_end}</p>
                      {r.notes && <p>Notes: {r.notes}</p>}
                    </div>
                  </div>
                  <div className="flex flex-col gap-1.5 shrink-0">
                    {['open', 'matching'].includes(r.status) && (
                      <button
                        onClick={() => rematch(r)}
                        disabled={rematching === r.request_id}
                        className="flex items-center gap-1 text-xs text-indigo-600 hover:text-indigo-700 bg-indigo-50 hover:bg-indigo-100 px-2.5 py-1 rounded-lg"
                      >
                        {rematching === r.request_id ? <Loader2 className="w-3 h-3 animate-spin" /> : <RefreshCw className="w-3 h-3" />}
                        Re-match
                      </button>
                    )}
                    {['open', 'matching', 'matched'].includes(r.status) && (
                      <button
                        onClick={() => cancelRequest(r.request_id)}
                        disabled={cancelling === r.request_id}
                        className="flex items-center gap-1 text-xs text-red-600 hover:text-red-700 bg-red-50 hover:bg-red-100 px-2.5 py-1 rounded-lg"
                      >
                        {cancelling === r.request_id ? <Loader2 className="w-3 h-3 animate-spin" /> : <X className="w-3 h-3" />}
                        Cancel
                      </button>
                    )}
                    {r.status === 'matched' && (
                      <div className="text-xs text-green-700 bg-green-50 px-2.5 py-1 rounded-lg flex items-center gap-1">
                        <CheckCircle className="w-3 h-3" />
                        Donor matched
                      </div>
                    )}
                    {r.status === 'fulfilled' && (
                      <div className="text-xs text-green-700 bg-green-50 px-2.5 py-1 rounded-lg flex items-center gap-1">
                        <CheckCircle className="w-3 h-3" />
                        Fulfilled
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}
