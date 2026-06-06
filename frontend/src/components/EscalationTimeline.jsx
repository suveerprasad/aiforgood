const STAGE_CONFIG = {
  open: { label: 'Request Created', color: 'bg-blue-500', textColor: 'text-blue-700', bgLight: 'bg-blue-50' },
  matching: { label: 'Finding Donors', color: 'bg-yellow-500', textColor: 'text-yellow-700', bgLight: 'bg-yellow-50' },
  matched: { label: 'Donor Matched', color: 'bg-indigo-500', textColor: 'text-indigo-700', bgLight: 'bg-indigo-50' },
  collecting: { label: 'Collection Scheduled', color: 'bg-purple-500', textColor: 'text-purple-700', bgLight: 'bg-purple-50' },
  fulfilled: { label: 'Fulfilled', color: 'bg-green-500', textColor: 'text-green-700', bgLight: 'bg-green-50' },
  escalated: { label: 'NGO Escalated', color: 'bg-orange-500', textColor: 'text-orange-700', bgLight: 'bg-orange-50' },
  cancelled: { label: 'Cancelled', color: 'bg-slate-400', textColor: 'text-slate-600', bgLight: 'bg-slate-50' },
}

const STATUS_ORDER = ['open', 'matching', 'matched', 'collecting', 'fulfilled']

export default function EscalationTimeline({ status, urgency, createdAt }) {
  const currentIndex = STATUS_ORDER.indexOf(status)
  const cfg = STAGE_CONFIG[status] || STAGE_CONFIG.open

  const urgencyBadge = {
    critical: 'bg-red-100 text-red-700',
    high: 'bg-orange-100 text-orange-700',
    standard: 'bg-green-100 text-green-700',
  }[urgency] || 'bg-slate-100 text-slate-600'

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${urgencyBadge}`}>
          {urgency?.toUpperCase()}
        </span>
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${cfg.bgLight} ${cfg.textColor}`}>
          {cfg.label}
        </span>
      </div>

      <div className="flex items-center gap-1">
        {STATUS_ORDER.map((step, i) => {
          const stepCfg = STAGE_CONFIG[step]
          const done = i <= currentIndex
          const active = i === currentIndex
          return (
            <div key={step} className="flex items-center gap-1">
              <div
                className={`w-2.5 h-2.5 rounded-full transition-colors ${
                  done ? stepCfg.color : 'bg-slate-200'
                } ${active ? 'ring-2 ring-offset-1 ring-current' : ''}`}
              />
              {i < STATUS_ORDER.length - 1 && (
                <div className={`h-0.5 w-6 ${done && i < currentIndex ? 'bg-green-400' : 'bg-slate-200'}`} />
              )}
            </div>
          )
        })}
      </div>
      {createdAt && (
        <p className="text-xs text-slate-400">
          Created {new Date(createdAt).toLocaleString('en-IN')}
        </p>
      )}
    </div>
  )
}
