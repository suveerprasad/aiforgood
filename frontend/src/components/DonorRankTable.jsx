import { MapPin, CheckCircle, XCircle, Phone, Mail } from 'lucide-react'

const ScoreBar = ({ value, color = 'bg-red-500' }) => (
  <div className="flex items-center gap-2">
    <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
      <div
        className={`h-full rounded-full ${color} transition-all`}
        style={{ width: `${Math.min(Math.max(value * 100, 0), 100)}%` }}
      />
    </div>
    <span className="text-xs text-slate-500 w-7 text-right">{Math.round(value * 100)}</span>
  </div>
)

const roleBadge = {
  'Bridge Donor': 'bg-purple-100 text-purple-700',
  'Emergency Donor': 'bg-red-100 text-red-700',
  'Guest': 'bg-blue-100 text-blue-700',
  'Volunteer': 'bg-teal-100 text-teal-700',
  'Patient': 'bg-orange-100 text-orange-700',
}

export default function DonorRankTable({ donors, loading }) {
  if (loading) return <div className="py-10 text-center text-slate-400 text-sm">Loading donors…</div>
  if (!donors?.length) return <div className="py-10 text-center text-slate-400 text-sm">No donors found</div>

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-slate-100">
            {['#', 'Donor ID', 'Blood', 'Role', 'Eligibility', 'Active Status', 'Score', 'Contact'].map(h => (
              <th key={h} className="text-left py-2 px-3 text-xs font-semibold text-slate-500 uppercase tracking-wide">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-slate-50">
          {donors.map((d, i) => {
            const rawScore = d.donor_score ?? d.calls_to_donations_ratio ?? 0
            const score = typeof rawScore === 'string' ? parseFloat(rawScore) : rawScore
            const isEligible = d.eligibility_status === 'eligible'
            const isActive = d.user_donation_active_status === 'Active'

            return (
              <tr key={d.user_id} className="hover:bg-slate-50 transition-colors">
                <td className="py-2 px-3 text-slate-400 font-mono text-xs">{i + 1}</td>
                <td className="py-2 px-3">
                  <div>
                    <span className="font-mono text-xs text-slate-700">{d.user_id?.slice(0, 10)}…</span>
                    {d.name && <p className="text-xs text-slate-500">{d.name}</p>}
                  </div>
                </td>
                <td className="py-2 px-3">
                  <span className="text-xs font-semibold text-red-700 bg-red-50 px-1.5 py-0.5 rounded">
                    {d.blood_group || '—'}
                  </span>
                </td>
                <td className="py-2 px-3">
                  <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${roleBadge[d.role] || 'bg-slate-100 text-slate-600'}`}>
                    {d.role || '—'}
                  </span>
                </td>
                <td className="py-2 px-3">
                  {isEligible
                    ? <span className="flex items-center gap-1 text-xs text-green-700"><CheckCircle className="w-3 h-3" />Eligible</span>
                    : <span className="flex items-center gap-1 text-xs text-slate-400"><XCircle className="w-3 h-3" />Not eligible</span>
                  }
                </td>
                <td className="py-2 px-3">
                  <span className={`text-xs px-2 py-0.5 rounded-full ${isActive ? 'bg-green-50 text-green-700' : 'bg-slate-100 text-slate-500'}`}>
                    {d.user_donation_active_status || '—'}
                  </span>
                </td>
                <td className="py-2 px-3 w-28">
                  <ScoreBar value={isNaN(score) ? 0 : score} />
                </td>
                <td className="py-2 px-3">
                  <div className="flex gap-1.5">
                    {d.email && (
                      <a href={`mailto:${d.email}`} className="text-slate-400 hover:text-blue-600">
                        <Mail className="w-3.5 h-3.5" />
                      </a>
                    )}
                    {d.phone_number && (
                      <a href={`tel:${d.phone_number}`} className="text-slate-400 hover:text-green-600">
                        <Phone className="w-3.5 h-3.5" />
                      </a>
                    )}
                    {!d.email && !d.phone_number && <span className="text-slate-300 text-xs">—</span>}
                  </div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
