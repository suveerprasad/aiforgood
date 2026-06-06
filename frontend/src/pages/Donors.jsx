import { useEffect, useState } from 'react'
import Navbar from '../components/layout/Navbar'
import DonorRankTable from '../components/DonorRankTable'
import DonorChatWidget from '../components/DonorChatWidget'
import { listDonors, updateConsent } from '../services/api'
import { Search, Filter, Users } from 'lucide-react'

const BLOOD_GROUPS = ['', 'O Positive', 'O Negative', 'A Positive', 'A Negative', 'B Positive', 'B Negative', 'AB Positive', 'AB Negative']
const ROLES = ['', 'Bridge Donor', 'Emergency Donor', 'Guest', 'Volunteer']

export default function Donors() {
  const [donors, setDonors] = useState([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({ role: '', blood_group: '', eligible_only: false })
  const [search, setSearch] = useState('')

  const load = () => {
    setLoading(true)
    const params = {}
    if (filters.role) params.role = filters.role
    if (filters.blood_group) params.blood_group = filters.blood_group
    if (filters.eligible_only) params.eligible_only = true
    listDonors(params).then(r => setDonors(r.data.donors || [])).finally(() => setLoading(false))
  }

  useEffect(() => { load() }, [filters])

  const filtered = search
    ? donors.filter(d => d.user_id?.includes(search) || d.blood_group?.toLowerCase().includes(search.toLowerCase()))
    : donors

  const stats = {
    total: donors.length,
    eligible: donors.filter(d => d.eligibility_status === 'eligible').length,
    active: donors.filter(d => d.user_donation_active_status === 'Active').length,
    bridge: donors.filter(d => d.role === 'Bridge Donor').length,
  }

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <Navbar title="Donors" subtitle="Manage and rank donor pool" />
      <div className="flex-1 overflow-y-auto p-6 space-y-5">

        {/* Stats */}
        <div className="grid grid-cols-4 gap-4">
          {[
            { label: 'Total Donors', value: stats.total, color: 'text-slate-800' },
            { label: 'Eligible Now', value: stats.eligible, color: 'text-green-700' },
            { label: 'Active', value: stats.active, color: 'text-blue-700' },
            { label: 'Bridge Donors', value: stats.bridge, color: 'text-purple-700' },
          ].map(s => (
            <div key={s.label} className="bg-white rounded-xl border border-slate-200 p-4">
              <p className="text-xs text-slate-500">{s.label}</p>
              <p className={`text-2xl font-bold mt-1 ${s.color}`}>{s.value}</p>
            </div>
          ))}
        </div>

        {/* Filters */}
        <div className="bg-white border border-slate-200 rounded-xl p-4 flex flex-wrap items-center gap-3">
          <div className="flex items-center gap-2 flex-1 min-w-48">
            <Search className="w-4 h-4 text-slate-400" />
            <input
              value={search}
              onChange={e => setSearch(e.target.value)}
              placeholder="Search by ID or blood group…"
              className="flex-1 text-sm outline-none text-slate-800 placeholder-slate-400"
            />
          </div>
          <select value={filters.role} onChange={e => setFilters({ ...filters, role: e.target.value })}
            className="text-sm border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none">
            {ROLES.map(r => <option key={r} value={r}>{r || 'All Roles'}</option>)}
          </select>
          <select value={filters.blood_group} onChange={e => setFilters({ ...filters, blood_group: e.target.value })}
            className="text-sm border border-slate-200 rounded-lg px-3 py-1.5 focus:outline-none">
            {BLOOD_GROUPS.map(bg => <option key={bg} value={bg}>{bg || 'All Blood Groups'}</option>)}
          </select>
          <label className="flex items-center gap-2 text-sm text-slate-600 cursor-pointer">
            <input type="checkbox" checked={filters.eligible_only}
              onChange={e => setFilters({ ...filters, eligible_only: e.target.checked })}
              className="rounded" />
            Eligible only
          </label>
        </div>

        {/* Table */}
        <div className="bg-white border border-slate-200 rounded-xl p-5">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-slate-900">
              {filtered.length} donor{filtered.length !== 1 ? 's' : ''} found
            </h3>
          </div>
          <DonorRankTable donors={filtered} loading={loading} />
        </div>
      </div>

      {/* Chat widget for donor interactions */}
      <DonorChatWidget />
    </div>
  )
}
