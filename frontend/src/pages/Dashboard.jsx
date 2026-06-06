import { useEffect, useState } from 'react'
import Navbar from '../components/layout/Navbar'
import DemandBarChart from '../components/DemandBarChart'
import InventoryExpiryAlert from '../components/InventoryExpiryAlert'
import EscalationTimeline from '../components/EscalationTimeline'
import { getDemandForecast, listRequests, getExpiryAlerts, getUrgencyQueue } from '../services/api'
import { Droplets, Users, Package, AlertTriangle, TrendingUp } from 'lucide-react'

const StatCard = ({ label, value, icon: Icon, color, sub }) => (
  <div className="bg-white rounded-xl border border-slate-200 p-5">
    <div className="flex items-start justify-between">
      <div>
        <p className="text-sm text-slate-500">{label}</p>
        <p className={`text-2xl font-bold mt-1 ${color}`}>{value ?? '—'}</p>
        {sub && <p className="text-xs text-slate-400 mt-0.5">{sub}</p>}
      </div>
      <div className={`w-10 h-10 rounded-xl flex items-center justify-center ${color === 'text-red-600' ? 'bg-red-50' : 'bg-blue-50'}`}>
        <Icon className={`w-5 h-5 ${color}`} />
      </div>
    </div>
  </div>
)

const urgencyColor = { critical: 'text-red-600 bg-red-50', high: 'text-orange-600 bg-orange-50', standard: 'text-green-600 bg-green-50' }

export default function Dashboard() {
  const [forecast, setForecast] = useState({})
  const [requests, setRequests] = useState([])
  const [expiring, setExpiring] = useState([])
  const [urgentQueue, setUrgentQueue] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    Promise.allSettled([
      getDemandForecast(7).then(r => setForecast(r.data.forecast)),
      listRequests({ limit: 10 }).then(r => setRequests(r.data.requests || [])),
      getExpiryAlerts().then(r => setExpiring(r.data.expiring_soon || [])),
      getUrgencyQueue(7).then(r => setUrgentQueue(r.data.upcoming || [])),
    ]).finally(() => setLoading(false))
  }, [])

  const totalUnits = Object.values(forecast).reduce((a, b) => a + b, 0)
  const openReqs = requests.filter(r => ['open', 'matching', 'matched'].includes(r.status)).length
  const criticalCount = urgentQueue.filter(p => p.urgency === 'critical').length

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <Navbar title="Dashboard" subtitle="Blood coordination overview" />
      <div className="flex-1 overflow-y-auto p-6 space-y-6">

        {/* Stats */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard label="Units Needed (7d)" value={totalUnits} icon={Droplets} color="text-red-600" sub="Across all blood groups" />
          <StatCard label="Open Requests" value={openReqs} icon={TrendingUp} color="text-blue-600" sub="Awaiting fulfilment" />
          <StatCard label="Critical Cases" value={criticalCount} icon={AlertTriangle} color="text-red-600" sub="≤ 3 days to transfusion" />
          <StatCard label="Expiring Units" value={expiring.length} icon={Package} color="text-orange-600" sub="Within 5 days" />
        </div>

        {/* Expiry alert */}
        {expiring.length > 0 && <InventoryExpiryAlert units={expiring} />}

        {/* Main grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Demand chart */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="font-semibold text-slate-900">7-Day Blood Demand</h3>
                <p className="text-xs text-slate-500 mt-0.5">Units required by blood group</p>
              </div>
              <span className="text-xs bg-red-50 text-red-700 px-2 py-0.5 rounded-full font-medium">Live</span>
            </div>
            <DemandBarChart forecast={forecast} loading={loading} />
          </div>

          {/* Urgency queue */}
          <div className="bg-white rounded-xl border border-slate-200 p-5">
            <h3 className="font-semibold text-slate-900 mb-4">Urgency Queue</h3>
            <div className="space-y-2 max-h-52 overflow-y-auto scrollbar-thin">
              {urgentQueue.length === 0 ? (
                <p className="text-sm text-slate-400 py-6 text-center">No upcoming transfusions in 7 days</p>
              ) : urgentQueue.map((p, i) => (
                <div key={i} className="flex items-center justify-between py-2 border-b border-slate-50 last:border-0">
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${urgencyColor[p.urgency]}`}>
                      {p.urgency.toUpperCase()}
                    </span>
                    <span className="text-sm font-semibold text-red-700">{p.blood_group}</span>
                    <span className="text-xs text-slate-500">{p.units} unit{p.units > 1 ? 's' : ''}</span>
                  </div>
                  <span className="text-xs text-slate-400">{p.days_until}d away</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Recent requests */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <h3 className="font-semibold text-slate-900 mb-4">Recent Requests</h3>
          {requests.length === 0
            ? <p className="text-sm text-slate-400 text-center py-4">No requests yet</p>
            : (
              <div className="space-y-2">
                {requests.slice(0, 6).map(r => (
                  <div key={r.request_id} className="flex items-center justify-between py-2 border-b border-slate-50 last:border-0">
                    <div>
                      <p className="text-sm font-medium text-slate-800">{r.blood_group} — {r.units_needed} unit{r.units_needed > 1 ? 's' : ''}</p>
                      <EscalationTimeline status={r.status} urgency={r.urgency_level} createdAt={r.created_at} />
                    </div>
                    <span className="font-mono text-xs text-slate-400">{r.request_id?.slice(0, 8)}…</span>
                  </div>
                ))}
              </div>
            )
          }
        </div>

      </div>
    </div>
  )
}
