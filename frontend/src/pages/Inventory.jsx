import { useEffect, useState } from 'react'
import Navbar from '../components/layout/Navbar'
import InventoryExpiryAlert from '../components/InventoryExpiryAlert'
import { getInventorySummary, getExpiryAlerts, addBloodUnit, checkInventory } from '../services/api'
import { Plus, Package2, Loader2 } from 'lucide-react'

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
  const [loading, setLoading] = useState(true)
  const [showAdd, setShowAdd] = useState(false)
  const [addForm, setAddForm] = useState({ blood_group: 'O Positive', donor_id: '' })
  const [adding, setAdding] = useState(false)

  const load = () => {
    setLoading(true)
    Promise.allSettled([
      getInventorySummary().then(r => setSummary(r.data.summary || [])),
      getExpiryAlerts().then(r => setExpiring(r.data.expiring_soon || [])),
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
                    ? (
                      <tr><td colSpan={5} className="text-center py-8 text-slate-400">No inventory data</td></tr>
                    )
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
