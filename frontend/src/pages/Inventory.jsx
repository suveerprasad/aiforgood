import { useEffect, useState } from 'react'
import Navbar from '../components/layout/Navbar'
import InventoryExpiryAlert from '../components/InventoryExpiryAlert'
import { getInventorySummary, getExpiryAlerts, addBloodUnit, issueBloodUnits, releaseBloodUnits, listRequests } from '../services/api'
import { Plus, Package2, Loader2, CheckCircle, RefreshCw } from 'lucide-react'

const BLOOD_GROUPS = ['O Positive', 'O Negative', 'A Positive', 'A Negative', 'B Positive', 'B Negative', 'AB Positive', 'AB Negative']

const StatusBar = ({ available, reserved, total }) => {
  const pct = total > 0 ? (available / total) * 100 : 0
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
        <div className="h-full bg-green-500 rounded-full" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-xs text-slate-500">{available}/{total}</span>
    </div>
  )
}

export default function Inventory() {
  const [summary, setSummary] = useState([])
  const [expiring, setExpiring] = useState([])
  const [matchedRequests, setMatchedRequests] = useState([])
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [addForm, setAddForm] = useState({ blood_group: 'O Positive', donor_id: '' })
  const [adding, setAdding] = useState(false)
  const [actionLoading, setActionLoading] = useState(null)
  const [actionResult, setActionResult] = useState(null)

  const load = () => {
    setLoading(true)
    Promise.allSettled([
      getInventorySummary().then(r => setSummary(r.data.summary || [])),
      getExpiryAlerts().then(r => setExpiring(r.data.expiring_soon || [])),
      // Show matched + open requests that may have donors committed via volunteer
      listRequests({ limit: 50 }).then(r => {
        const active = (r.data.requests || []).filter(req =>
          ['matched', 'open', 'matching'].includes(req.status)
        )
        setMatchedRequests(active)
      }),
    ]).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [])

  const handleAdd = async (e) => {
    e.preventDefault()
    setAdding(true)
    try {
      await addBloodUnit(addForm)
      setShowAdd(false)
      load()
    } finally {
      setAdding(false)
    }
  }

  const handleIssue = async (requestId) => {
    setActionLoading(`issue-${requestId}`)
    setActionResult(null)
    try {
      const r = await issueBloodUnits(requestId)
      setActionResult({ type: 'success', msg: `Issued ${r.data.units_issued} unit(s) for request ${requestId.slice(0, 8)}` })
      load()
    } catch (err) {
      setActionResult({ type: 'error', msg: err.response?.data?.detail || 'Issue failed' })
    } finally {
      setActionLoading(null)
    }
  }

  const handleRelease = async (requestId) => {
    if (!window.confirm('Release reserved units back to available stock?')) return
    setActionLoading(`release-${requestId}`)
    setActionResult(null)
    try {
      const r = await releaseBloodUnits(requestId)
      setActionResult({ type: 'success', msg: `Released ${r.data.units_released} unit(s) back to stock` })
      load()
    } catch (err) {
      setActionResult({ type: 'error', msg: err.response?.data?.detail || 'Release failed' })
    } finally {
      setActionLoading(null)
    }
  }

  const totalAvailable = summary.reduce((a, s) => a + (s.available || 0), 0)
  const totalReserved = summary.reduce((a, s) => a + (s.reserved || 0), 0)
  const totalExpiring = summary.reduce((a, s) => a + (s.expiring_soon || 0), 0)

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <Navbar title="Inventory" subtitle="Blood unit stock management" />
      <div className="flex-1 overflow-y-auto p-6 space-y-5">

        {/* Stats */}
        <div className="grid grid-cols-3 gap-4">
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <p className="text-xs text-slate-500">Available Units</p>
            <p className="text-2xl font-bold text-green-700 mt-1">{totalAvailable}</p>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <p className="text-xs text-slate-500">Reserved Units</p>
            <p className="text-2xl font-bold text-blue-700 mt-1">{totalReserved}</p>
          </div>
          <div className="bg-white rounded-xl border border-slate-200 p-4">
            <p className="text-xs text-slate-500">Expiring Soon</p>
            <p className="text-2xl font-bold text-orange-700 mt-1">{totalExpiring}</p>
          </div>
        </div>

        <InventoryExpiryAlert units={expiring} />

        {/* Action result toast */}
        {actionResult && (
          <div className={`text-sm px-4 py-3 rounded-lg ${
            actionResult.type === 'success' ? 'bg-green-50 text-green-700 border border-green-200'
            : 'bg-red-50 text-red-700 border border-red-200'
          }`}>
            {actionResult.msg}
            {actionResult.type === 'error' && actionResult.msg.includes('No blood units') && (
              <span className="ml-2 text-xs">
                → Ask the donor to re-confirm via their portal, or use "Add Blood Unit" below.
              </span>
            )}
          </div>
        )}

        {/* Matched requests — Issue / Release */}
        {matchedRequests.length > 0 && (
          <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
            <div className="p-4 border-b border-slate-100 flex items-center justify-between">
              <h3 className="font-semibold text-slate-900 text-sm">Active Requests — Issue / Release Blood Units</h3>
              <span className="text-xs text-slate-400">{matchedRequests.length} active request{matchedRequests.length !== 1 ? 's' : ''}</span>
            </div>
            <table className="w-full text-sm">
              <thead className="bg-slate-50">
                <tr>
                  {['Request ID', 'Blood Group', 'Units', 'Urgency', 'Actions'].map(h => (
                    <th key={h} className="text-left py-2.5 px-4 text-xs font-semibold text-slate-500">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-50">
                {matchedRequests.map(r => (
                  <tr key={r.request_id} className="hover:bg-slate-50">
                    <td className="py-2.5 px-4 font-mono text-xs text-slate-500">{r.request_id?.slice(0, 8)}…</td>
                    <td className="py-2.5 px-4">
                      <span className="text-xs font-bold text-red-700 bg-red-50 px-2 py-0.5 rounded">{r.blood_group}</span>
                    </td>
                    <td className="py-2.5 px-4 text-slate-700">{r.units_needed}</td>
                    <td className="py-2.5 px-4">
                      <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${
                        r.urgency_level === 'critical' ? 'bg-red-100 text-red-700'
                        : r.urgency_level === 'high' ? 'bg-orange-100 text-orange-700'
                        : 'bg-green-100 text-green-700'
                      }`}>{r.urgency_level}</span>
                    </td>
                    <td className="py-2.5 px-4">
                      <div className="flex gap-2">
                        <button
                          onClick={() => handleIssue(r.request_id)}
                          disabled={!!actionLoading}
                          className="flex items-center gap-1 text-xs bg-green-600 hover:bg-green-700 text-white px-2.5 py-1 rounded-lg font-medium"
                        >
                          {actionLoading === `issue-${r.request_id}`
                            ? <Loader2 className="w-3 h-3 animate-spin" />
                            : <CheckCircle className="w-3 h-3" />}
                          Issue (Transfused)
                        </button>
                        <button
                          onClick={() => handleRelease(r.request_id)}
                          disabled={!!actionLoading}
                          className="flex items-center gap-1 text-xs bg-slate-100 hover:bg-slate-200 text-slate-700 px-2.5 py-1 rounded-lg font-medium"
                        >
                          {actionLoading === `release-${r.request_id}`
                            ? <Loader2 className="w-3 h-3 animate-spin" />
                            : <RefreshCw className="w-3 h-3" />}
                          Release (Cancel)
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Add unit form */}
        <div className="flex justify-end">
          <button onClick={() => setShowAdd(!showAdd)}
            className="flex items-center gap-2 bg-red-600 hover:bg-red-700 text-white text-sm font-medium px-4 py-2 rounded-lg">
            <Plus className="w-4 h-4" /> Add Blood Unit
          </button>
        </div>

        {showAdd && (
          <div className="bg-white border border-slate-200 rounded-xl p-5">
            <h3 className="font-semibold text-slate-900 mb-4">Add New Blood Unit</h3>
            <form onSubmit={handleAdd} className="flex gap-4 items-end flex-wrap">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Blood Group</label>
                <select value={addForm.blood_group} onChange={e => setAddForm({ ...addForm, blood_group: e.target.value })}
                  className="border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none">
                  {BLOOD_GROUPS.map(bg => <option key={bg}>{bg}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1">Donor ID (optional)</label>
                <input value={addForm.donor_id} onChange={e => setAddForm({ ...addForm, donor_id: e.target.value })}
                  className="border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none w-48" placeholder="donor user_id" />
              </div>
              <button type="submit" disabled={adding}
                className="flex items-center gap-2 bg-green-600 hover:bg-green-700 text-white text-sm font-medium px-4 py-2 rounded-lg">
                {adding && <Loader2 className="w-4 h-4 animate-spin" />}
                Add Unit
              </button>
            </form>
          </div>
        )}

        {/* Summary table */}
        <div className="bg-white border border-slate-200 rounded-xl overflow-hidden">
          <div className="p-5 border-b border-slate-100">
            <h3 className="font-semibold text-slate-900">Inventory by Blood Group</h3>
          </div>
          {loading
            ? <div className="text-center py-10 text-slate-400">Loading…</div>
            : (
              <table className="w-full text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    {['Blood Group', 'Available', 'Reserved', 'Expiring Soon', 'Stock Level'].map(h => (
                      <th key={h} className="text-left py-3 px-4 text-xs font-semibold text-slate-500">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-50">
                  {summary.length === 0
                    ? <tr><td colSpan={5} className="text-center py-8 text-slate-400">No inventory data</td></tr>
                    : summary.sort((a, b) => b.available - a.available).map(s => (
                      <tr key={s.blood_group} className="hover:bg-slate-50">
                        <td className="py-3 px-4">
                          <span className="text-sm font-bold text-red-700 bg-red-50 px-2 py-0.5 rounded">{s.blood_group}</span>
                        </td>
                        <td className="py-3 px-4 text-green-700 font-semibold">{s.available}</td>
                        <td className="py-3 px-4 text-blue-600">{s.reserved}</td>
                        <td className="py-3 px-4">
                          {s.expiring_soon > 0
                            ? <span className="text-orange-600 font-semibold">{s.expiring_soon}</span>
                            : <span className="text-slate-400">0</span>}
                        </td>
                        <td className="py-3 px-4 w-40">
                          <StatusBar available={s.available} reserved={s.reserved} total={s.total || s.available + s.reserved} />
                        </td>
                      </tr>
                    ))
                  }
                </tbody>
              </table>
            )
          }
        </div>

      </div>
    </div>
  )
}
