import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { Activity, Loader2 } from 'lucide-react'

const BLOOD_GROUPS = ['O Positive', 'O Negative', 'A Positive', 'A Negative', 'B Positive', 'B Negative', 'AB Positive', 'AB Negative']

const ROLES = [
  { value: 'blood_bank', label: 'Blood Bank / Admin', desc: 'Manage requests, donors, inventory & AI insights' },
  { value: 'donor', label: 'Blood Donor', desc: 'View donation requests directed to you and respond' },
  { value: 'patient', label: 'Patient', desc: 'Submit blood requests and track fulfilment status' },
]

export default function Register() {
  const { register } = useAuth()
  const nav = useNavigate()
  const [form, setForm] = useState({
    email: '', password: '', confirmPassword: '', name: '',
    system_role: '', blood_group: 'O Positive',
    phone_number: '', latitude: '', longitude: '',
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    if (form.password !== form.confirmPassword) {
      setError('Passwords do not match')
      return
    }
    if (!form.system_role) {
      setError('Please select a role')
      return
    }
    setLoading(true)
    try {
      const payload = {
        email: form.email,
        password: form.password,
        name: form.name,
        system_role: form.system_role,
        blood_group: form.blood_group,
        phone_number: form.phone_number || null,
        latitude: form.latitude ? parseFloat(form.latitude) : null,
        longitude: form.longitude ? parseFloat(form.longitude) : null,
      }
      const user = await register(payload)
      if (user.system_role === 'donor') nav('/donor-portal')
      else if (user.system_role === 'patient') nav('/patient-portal')
      else nav('/')
    } catch (err) {
      setError(err.response?.data?.detail || 'Registration failed.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-red-50 via-white to-slate-50 flex items-center justify-center p-4">
      <div className="w-full max-w-lg">
        {/* Logo */}
        <div className="text-center mb-6">
          <div className="inline-flex items-center justify-center w-14 h-14 bg-red-600 rounded-2xl shadow-lg mb-3">
            <Activity className="w-7 h-7 text-white" />
          </div>
          <h1 className="text-2xl font-bold text-slate-900">Create Account</h1>
          <p className="text-slate-500 text-sm mt-1">BloodBridge AI — Blood Coordination Platform</p>
        </div>

        <div className="bg-white rounded-2xl border border-slate-200 shadow-sm p-8">
          {error && (
            <div className="bg-red-50 border border-red-200 text-red-700 text-sm rounded-lg px-4 py-3 mb-5">
              {error}
            </div>
          )}

          <form onSubmit={submit} className="space-y-5">
            {/* Role selection */}
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-2">Select your role *</label>
              <div className="grid grid-cols-1 gap-2">
                {ROLES.map(r => (
                  <label key={r.value} className={`flex items-start gap-3 p-3 border rounded-xl cursor-pointer transition-colors ${
                    form.system_role === r.value ? 'border-red-400 bg-red-50' : 'border-slate-200 hover:border-slate-300'
                  }`}>
                    <input type="radio" name="system_role" value={r.value}
                      checked={form.system_role === r.value}
                      onChange={e => setForm({ ...form, system_role: e.target.value })}
                      className="mt-0.5 accent-red-600" />
                    <div>
                      <p className="text-sm font-medium text-slate-800">{r.label}</p>
                      <p className="text-xs text-slate-500">{r.desc}</p>
                    </div>
                  </label>
                ))}
              </div>
            </div>

            {/* Basic info */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1.5">Full Name *</label>
                <input required value={form.name} onChange={e => setForm({ ...form, name: e.target.value })}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-red-400"
                  placeholder="Your name" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1.5">Blood Group *</label>
                <select value={form.blood_group} onChange={e => setForm({ ...form, blood_group: e.target.value })}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-red-400">
                  {BLOOD_GROUPS.map(bg => <option key={bg}>{bg}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1.5">Email address *</label>
                <input required type="email" value={form.email} onChange={e => setForm({ ...form, email: e.target.value })}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-red-400"
                  placeholder="you@example.com" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1.5">Phone Number</label>
                <input type="tel" value={form.phone_number} onChange={e => setForm({ ...form, phone_number: e.target.value })}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-red-400"
                  placeholder="+91 9876543210" />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1.5">Password *</label>
                <input required type="password" value={form.password} onChange={e => setForm({ ...form, password: e.target.value })}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-red-400"
                  placeholder="Minimum 6 characters" minLength={6} />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-600 mb-1.5">Confirm Password *</label>
                <input required type="password" value={form.confirmPassword} onChange={e => setForm({ ...form, confirmPassword: e.target.value })}
                  className="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-red-400"
                  placeholder="Repeat password" />
              </div>
            </div>

            {/* Optional location (for donors / patients) */}
            {(form.system_role === 'donor' || form.system_role === 'patient') && (
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1.5">Latitude (optional)</label>
                  <input type="number" step="any" value={form.latitude} onChange={e => setForm({ ...form, latitude: e.target.value })}
                    className="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-red-400"
                    placeholder="e.g. 17.3850" />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-600 mb-1.5">Longitude (optional)</label>
                  <input type="number" step="any" value={form.longitude} onChange={e => setForm({ ...form, longitude: e.target.value })}
                    className="w-full border border-slate-200 rounded-lg px-3 py-2.5 text-sm focus:outline-none focus:border-red-400"
                    placeholder="e.g. 78.4867" />
                </div>
              </div>
            )}

            <button type="submit" disabled={loading}
              className="w-full flex items-center justify-center gap-2 bg-red-600 hover:bg-red-700 disabled:opacity-60 text-white font-medium py-2.5 rounded-lg transition-colors">
              {loading && <Loader2 className="w-4 h-4 animate-spin" />}
              Create Account
            </button>
          </form>

          <div className="mt-5 pt-4 border-t border-slate-100 text-center">
            <p className="text-sm text-slate-500">
              Already have an account?{' '}
              <Link to="/login" className="text-red-600 font-medium hover:underline">Sign in</Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
