import { MapPin, Star, CheckCircle, XCircle } from 'lucide-react'

const ScoreBar = ({ value, color = 'bg-red-500' }) => (
  <div className="flex items-center gap-2">
    <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
      <div
        className={`h-full rounded-full ${color} transition-all`}
        style={{ width: `${Math.min(value, 100)}%` }}
      />
    </div>
    <span className="text-xs text-slate-500 w-7 text-right">{Math.round(value)}</span>
  </div>
)

const stageBadge = {
  bridge: 'bg-purple-100 text-purple-700',
  emergency: 'bg-red-100 text-red-700',
  regional: 'bg-blue-100 text-blue-700',
  ngo: 'bg-orange-100 text-orange-700',
}

export default function DonorRankTable({ donors, loading }) {
  if (loading) {
    return <div className="py-10 text-center text-slate-400 text-sm">Ranking donors...</div>
  }
  if (!donors?.length) {
    return <div className="py-10 text-center text-slate-400 text-sm">No donors found</div>
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-100">
            <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">#</th>
            <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Donor ID</th>
            <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Blood</th>
            <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Stage</th>
            <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Score</th>
            <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Distance</th>
            <th className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">Eligible</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-50">
          {donors.map((d, i) => (
            <tr key={d.user_id} className="hover:bg-slate-50 transition-colors">
              <td className="py-2 px-3 text-slate-400 font-mono text-xs">{i + 1}</td>
              <td className="py-2 px-3">
                <span className="font-mono text-xs text-slate-700">{d.user_id?.slice(0, 8)}…</span>
              </td>
              <td className="py-2 px-3">
                <span className="text-xs font-semibold text-red-700 bg-red-50 px-1.5 py-0.5 rounded">
                  {d.blood_group || '—'}
                </span>
              </td>
              <td className="py-2 px-3">
                <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${stageBadge[d.stage] || 'bg-slate-100 text-slate-600'}`}>
                  {d.stage || '—'}
                </span>
              </td>
              <td className="py-2 px-3 w-32">
                <ScoreBar value={d.donor_score || 0} />
              </td>
              <td className="py-2 px-3">
                <span className="flex items-center gap-1 text-xs text-slate-600">
                  <MapPin className="w-3 h-3 text-slate-400" />
                  {d.distance_km != null ? `${d.distance_km} km` : '—'}
                </span>
              </td>
              <td className="py-2 px-3">
                {d.is_eligible
                  ? <CheckCircle className="w-4 h-4 text-green-500" />
                  : <XCircle className="w-4 h-4 text-red-400" />
                }
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
