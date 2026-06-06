import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell
} from 'recharts'

const BLOOD_GROUP_COLORS = {
  'O Positive': '#ef4444',
  'O Negative': '#dc2626',
  'A Positive': '#f97316',
  'A Negative': '#ea580c',
  'B Positive': '#3b82f6',
  'B Negative': '#2563eb',
  'AB Positive': '#8b5cf6',
  'AB Negative': '#7c3aed',
  'Other': '#94a3b8',
}

const CustomTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null
  return (
    <div className="bg-white border border-slate-200 rounded-lg p-3 shadow-lg text-sm">
      <p className="font-medium text-slate-900">{label}</p>
      <p className="text-red-600 font-semibold mt-1">{payload[0].value} units needed</p>
    </div>
  )
}

export default function DemandBarChart({ forecast, loading }) {
  if (loading) {
    return (
      <div className="h-56 flex items-center justify-center text-slate-400 text-sm">
        Loading forecast...
      </div>
    )
  }

  const data = Object.entries(forecast || {})
    .filter(([, v]) => v > 0)
    .map(([blood_group, units]) => ({ blood_group, units }))
    .sort((a, b) => b.units - a.units)

  if (!data.length) {
    return (
      <div className="h-56 flex items-center justify-center text-slate-400 text-sm">
        No demand forecast available
      </div>
    )
  }

  return (
    <ResponsiveContainer width="100%" height={220}>
      <BarChart data={data} margin={{ top: 5, right: 10, left: -20, bottom: 5 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
        <XAxis
          dataKey="blood_group"
          tick={{ fontSize: 11, fill: '#64748b' }}
          tickLine={false}
          axisLine={false}
        />
        <YAxis
          tick={{ fontSize: 11, fill: '#64748b' }}
          tickLine={false}
          axisLine={false}
        />
        <Tooltip content={<CustomTooltip />} />
        <Bar dataKey="units" radius={[4, 4, 0, 0]}>
          {data.map((entry) => (
            <Cell
              key={entry.blood_group}
              fill={BLOOD_GROUP_COLORS[entry.blood_group] || '#ef4444'}
            />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}
