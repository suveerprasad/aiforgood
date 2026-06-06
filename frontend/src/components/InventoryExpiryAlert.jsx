import { AlertTriangle, Clock } from 'lucide-react'

export default function InventoryExpiryAlert({ units }) {
  if (!units?.length) return null

  return (
    <div className="rounded-xl border border-orange-200 bg-orange-50 p-4">
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-orange-500 flex-shrink-0 mt-0.5" />
        <div className="flex-1">
          <h4 className="text-sm font-semibold text-orange-800">
            {units.length} unit{units.length > 1 ? 's' : ''} expiring within 5 days
          </h4>
          <p className="text-xs text-orange-600 mt-0.5 mb-3">
            Act now to prevent blood wastage — reallocate or issue these units.
          </p>
          <div className="space-y-2">
            {units.slice(0, 5).map((unit) => (
              <div key={unit.blood_unit_id} className="flex items-center justify-between bg-white rounded-lg px-3 py-2 border border-orange-100">
                <div className="flex items-center gap-2">
                  <span className="text-xs font-bold text-red-700 bg-red-50 px-1.5 py-0.5 rounded">
                    {unit.blood_group}
                  </span>
                  <span className="text-xs text-slate-500 font-mono">{unit.blood_unit_id?.slice(0, 8)}…</span>
                </div>
                <div className="flex items-center gap-1 text-xs text-orange-600 font-medium">
                  <Clock className="w-3 h-3" />
                  {unit.expiry_date}
                </div>
              </div>
            ))}
            {units.length > 5 && (
              <p className="text-xs text-orange-500 text-center">+{units.length - 5} more units</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
