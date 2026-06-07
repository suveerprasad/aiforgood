/**
 * Donor Portal — shown to users with system_role = "donor"
 *
 * Sections:
 * 1. Profile card (blood group, eligibility, donation stats)
 * 2. Compatible open requests — donor can VOLUNTEER directly
 * 3. Notifications sent to this donor — with Confirm/Decline buttons
 * 4. Consent toggle
 * 5. Chat widget
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../contexts/AuthContext'
import { getDonor, updateConsent, getEligibleRequests, getDonorNotifications, donorVolunteer, recordDonorResponse } from '../services/api'
import {
  Activity, CheckCircle, XCircle, Calendar, LogOut,
  Loader2, Heart, Bell, MapPin, Clock, Navigation, User, Droplets, AlertTriangle
} from 'lucide-react'
import DonorChatWidget from '../components/DonorChatWidget'

// ── Request card shown to donor with all relevant details ─────────────────────
function RequestCard({ req, donorBloodGroup, isEligible, volunteering, onVolunteer }) {
  const urgencyStyle = {
    critical: { badge: 'bg-red-100 text-red-700 border-red-200', border: 'border-red-300 bg-red-50', icon: <AlertTriangle className="w-3.5 h-3.5 text-red-600" /> },
    high:     { badge: 'bg-orange-100 text-orange-700 border-orange-200', border: 'border-orange-200 bg-orange-50', icon: <Clock className="w-3.5 h-3.5 text-orange-500" /> },
    standard: { badge: 'bg-green-100 text-green-700 border-green-200', border: 'border-slate-200 bg-white', icon: <CheckCircle className="w-3.5 h-3.5 text-green-500" /> },
  }
  const u = urgencyStyle[req.urgency_level] || urgencyStyle.standard

  const daysUntil = req.transfusion_date
    ? Math.ceil((new Date(req.transfusion_date) - new Date()) / 86400000)
    : null

  return (
    <div className={`border rounded-2xl p-5 transition-all ${u.border}`}>
      {/* Top row: blood group + urgency + volunteer button */}
      <div className="flex items-start justify-between gap-3 flex-wrap mb-4">
        <div className="flex items-center gap-2 flex-wrap">
          <span className="text-sm font-bold text-red-700 bg-white border border-red-200 px-3 py-1 rounded-full shadow-sm">
            🩸 {req.blood_group}
          </span>
          <span className={`text-xs font-semibold px-2.5 py-1 rounded-full border ${u.badge} flex items-center gap-1`}>
            {u.icon} {(req.urgency_level || 'standard').toUpperCase()}
          </span>
          {daysUntil !== null && daysUntil <= 3 && (
            <span className="text-xs font-bold text-red-600 bg-red-50 px-2 py-0.5 rounded-full animate-pulse">
              ⚡ {daysUntil <= 0 ? 'TODAY' : `${daysUntil}d left`}
            </span>
          )}
        </div>
        <button
          onClick={() => onVolunteer(req)}
          disabled={volunteering === req.request_id || !isEligible}
          className={`flex items-center gap-1.5 text-sm font-semibold px-4 py-2 rounded-xl shrink-0 transition-all shadow-sm
            ${isEligible
              ? 'bg-red-600 hover:bg-red-700 text-white'
              : 'bg-slate-100 text-slate-400 cursor-not-allowed'}`}
          title={!isEligible ? 'You are not eligible to donate right now' : 'Click to volunteer for this donation'}
        >
          {volunteering === req.request_id
            ? <Loader2 className="w-4 h-4 animate-spin" />
            : <Heart className="w-4 h-4" />}
          {volunteering === req.request_id ? 'Confirming…' : "I'm Available"}
        </button>
      </div>

      {/* Details grid */}
      <div className="grid grid-cols-2 gap-3">
        {/* Patient info */}
        <div className="bg-white bg-opacity-70 rounded-xl p-3 space-y-1">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Patient</p>
          <div className="flex items-center gap-1.5">
            <User className="w-3.5 h-3.5 text-slate-400" />
            <span className="text-sm font-medium text-slate-800">
              {req.patient_first_name || 'Patient'} (anonymous)
            </span>
          </div>
          <div className="flex items-center gap-1.5 text-xs text-slate-500">
            <Droplets className="w-3 h-3" />
            <span>Needs {req.units_needed} unit{req.units_needed > 1 ? 's' : ''} of {req.blood_group}</span>
          </div>
          {req.notes && (
            <p className="text-xs text-slate-500 mt-1 italic">"{req.notes}"</p>
          )}
        </div>

        {/* Location & timing */}
        <div className="bg-white bg-opacity-70 rounded-xl p-3 space-y-1">
          <p className="text-xs font-semibold text-slate-500 uppercase tracking-wide">Location & Time</p>
          {req.distance_km != null ? (
            <div className="flex items-center gap-1.5">
              <Navigation className="w-3.5 h-3.5 text-blue-500" />
              <span className="text-sm font-bold text-blue-700">
                {req.distance_km === 0
                  ? 'Same area'
                  : req.distance_km < 1
                    ? `${Math.round(req.distance_km * 1000)} m away`
                    : `${req.distance_km.toFixed(1)} km away`}
              </span>
            </div>
          ) : (
            <div className="flex items-center gap-1.5 text-xs text-slate-400">
              <MapPin className="w-3 h-3" /> Location not shared
            </div>
          )}
          {req.hospital && (
            <div className="flex items-center gap-1.5 text-xs text-slate-600">
              <MapPin className="w-3 h-3 text-slate-400" /> {req.hospital}
            </div>
          )}
          {req.transfusion_date && (
            <div className="flex items-center gap-1.5 text-xs text-slate-600">
              <Calendar className="w-3 h-3 text-slate-400" />
              Transfusion: <strong>{req.transfusion_date}</strong>
            </div>
          )}
          {req.collection_window_end && (
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <Clock className="w-3 h-3 text-slate-400" />
              Donate by: {req.collection_window_end}
            </div>
          )}
        </div>
      </div>

      {/* Compatibility note */}
      <div className="mt-3 flex items-center gap-1.5 text-xs text-green-700 bg-green-50 px-3 py-1.5 rounded-lg">
        <CheckCircle className="w-3.5 h-3.5 text-green-500" />
        Your blood group <strong>{donorBloodGroup}</strong> is compatible with this patient's needs.
      </div>
    </div>
  )
}

const urgencyStyle = {
  critical: 'bg-red-100 text-red-700 border-red-200',
  high: 'bg-orange-100 text-orange-700 border-orange-200',
  standard: 'bg-green-100 text-green-700 border-green-200',
}

export default function DonorPortal() {
  const { user, logout } = useAuth()
  const nav = useNavigate()
  const [profile, setProfile] = useState(null)
  const [openRequests, setOpenRequests] = useState([])
  const [notifications, setNotifications] = useState([])
  const [loading, setLoading] = useState(true)
  const [volunteering, setVolunteering] = useState(null)
  const [responding, setResponding] = useState(null)
  const [toast, setToast] = useState(null)

  useEffect(() => {
    if (!user) { nav('/login'); return }
    loadAll()
  }, [user])

  const showToast = (msg, type = 'success') => {
    setToast({ msg, type })
    setTimeout(() => setToast(null), 4000)
  }

  const loadAll = async () => {
    setLoading(true)
    try {
      const [profileRes, requestsRes, notifsRes] = await Promise.allSettled([
        getDonor(user.user_id),
        getEligibleRequests(user.user_id),
        getDonorNotifications(user.user_id),
      ])

      if (profileRes.status === 'fulfilled') setProfile(profileRes.value.data)
      if (requestsRes.status === 'fulfilled') setOpenRequests(requestsRes.value.data.requests || [])
      if (notifsRes.status === 'fulfilled') setNotifications(notifsRes.value.data.notifications || [])
    } finally {
      setLoading(false)
    }
  }

  const volunteer = async (req) => {
    setVolunteering(req.request_id)
    try {
      await donorVolunteer({
        donor_id: user.user_id,
        request_id: req.request_id,
        blood_group: req.blood_group,
      })
      showToast(`You're confirmed for the ${req.blood_group} donation! The blood bank will contact you shortly.`)
      loadAll()
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to volunteer', 'error')
    } finally {
      setVolunteering(null)
    }
  }

  const respond = async (notif, response) => {
    setResponding(notif.notification_id)
    try {
      await recordDonorResponse({
        donor_id: user.user_id,
        request_id: notif.request_id,
        notification_id: notif.notification_id,
        response,
      })
      showToast(response === 'confirmed'
        ? 'Donation confirmed! The blood bank will send you appointment details.'
        : 'Response recorded. Thank you for letting us know.')
      loadAll()
    } catch (err) {
      showToast(err.response?.data?.detail || 'Failed to record response', 'error')
    } finally {
      setResponding(null)
    }
  }

  const handleLogout = () => { logout(); nav('/login') }

  const blood_group = profile?.blood_group || user?.blood_group || '—'
  const eligibility = profile?.eligibility_status || 'eligible'
  const isEligible = eligibility === 'eligible'
  const donations = profile?.donations_till_date || 0
  const lastDonation = profile?.last_donation_date || 'No previous donation'
  const nextEligible = profile?.next_eligible_date || null

  // Filter out requests already responded to (from notifications)
  const respondedRequestIds = new Set(
    notifications.filter(n => n.status === 'responded').map(n => n.request_id)
  )
  const availableRequests = openRequests.filter(r => !respondedRequestIds.has(r.request_id))

  const pendingNotifs = notifications.filter(n => n.status === 'sent')
  const respondedNotifs = notifications.filter(n => n.status === 'responded')

  return (
    <div className="min-h-screen bg-slate-50">
      {/* Header */}
      <header className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-red-600 flex items-center justify-center">
            <Activity className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="font-bold text-slate-900 text-sm">BloodBridge AI</h1>
            <p className="text-xs text-slate-500">Donor Portal</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right">
            <p className="text-sm font-medium text-slate-800">{user?.name}</p>
            <p className="text-xs text-slate-500">Blood Donor</p>
          </div>
          <button onClick={handleLogout} className="p-2 rounded-lg hover:bg-slate-100 text-slate-500">
            <LogOut className="w-4 h-4" />
          </button>
        </div>
      </header>

      <div className="max-w-2xl mx-auto p-5 space-y-5">

        {/* Toast */}
        {toast && (
          <div className={`text-sm px-4 py-3 rounded-xl border ${
            toast.type === 'error' ? 'bg-red-50 text-red-700 border-red-200'
            : 'bg-green-50 text-green-700 border-green-200'
          }`}>
            {toast.msg}
          </div>
        )}

        {/* Profile card */}
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 rounded-full bg-red-600 flex items-center justify-center text-white text-xl font-bold shrink-0">
              {(user?.name || 'D')[0].toUpperCase()}
            </div>
            <div className="flex-1">
              <h2 className="text-base font-bold text-slate-900">{user?.name}</h2>
              <p className="text-xs text-slate-500">{user?.email}</p>
            </div>
            <div className="flex flex-col items-end gap-1.5">
              <span className="text-xs font-bold text-red-700 bg-red-50 px-3 py-1 rounded-full border border-red-200">
                {blood_group}
              </span>
              <span className={`text-xs font-medium px-3 py-1 rounded-full border ${
                isEligible ? 'bg-green-50 text-green-700 border-green-200' : 'bg-slate-100 text-slate-500 border-slate-200'
              }`}>
                {isEligible ? 'Eligible to Donate' : 'Not Eligible Yet'}
              </span>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-3 mt-4">
            <div className="bg-slate-50 rounded-xl p-3 text-center">
              <p className="text-xs text-slate-500">Total Donations</p>
              <p className="text-2xl font-bold text-red-700 mt-0.5">{donations}</p>
            </div>
            <div className="bg-slate-50 rounded-xl p-3 text-center">
              <p className="text-xs text-slate-500">Last Donation</p>
              <p className="text-xs font-semibold text-slate-700 mt-1">{lastDonation}</p>
            </div>
            <div className="bg-slate-50 rounded-xl p-3 text-center">
              <p className="text-xs text-slate-500">Next Eligible</p>
              <p className="text-xs font-semibold text-slate-700 mt-1">{nextEligible || 'Now'}</p>
            </div>
          </div>
        </div>

        {/* Ineligible warning */}
        {!isEligible && (
          <div className="bg-orange-50 border border-orange-200 rounded-xl p-4 flex items-start gap-3">
            <Clock className="w-5 h-5 text-orange-500 shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-orange-800">Donation cooldown active</p>
              <p className="text-xs text-orange-600 mt-0.5">
                You donated recently. You'll be eligible to donate again on{' '}
                <strong>{nextEligible || 'a future date'}</strong>. Thank you for your previous donation!
              </p>
            </div>
          </div>
        )}

        {/* Pending notifications from blood bank */}
        {pendingNotifs.length > 0 && (
          <div className="bg-white rounded-2xl border border-red-200 p-5">
            <div className="flex items-center gap-2 mb-4">
              <Bell className="w-5 h-5 text-red-600" />
              <h3 className="font-semibold text-slate-900">Donation Requests Sent to You</h3>
              <span className="text-xs bg-red-600 text-white px-2 py-0.5 rounded-full font-bold">{pendingNotifs.length}</span>
            </div>
            <div className="space-y-3">
              {pendingNotifs.map(notif => (
                <div key={notif.notification_id} className="border border-slate-200 rounded-xl p-4 bg-red-50">
                  <div className="flex items-start justify-between gap-3 flex-wrap">
                    <div>
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className="text-xs font-bold text-red-700 bg-white px-2 py-0.5 rounded border border-red-200">
                          {blood_group}
                        </span>
                        <span className={`text-xs px-2 py-0.5 rounded-full font-medium border ${urgencyStyle[notif.urgency] || urgencyStyle.standard}`}>
                          {(notif.urgency || 'standard').toUpperCase()}
                        </span>
                      </div>
                      <p className="text-sm text-slate-700">{notif.message_preview || 'A patient urgently needs your blood type.'}</p>
                      <p className="text-xs text-slate-400 mt-1 flex items-center gap-1">
                        <Calendar className="w-3 h-3" /> {notif.sent_at?.slice(0, 10)}
                      </p>
                    </div>
                    <div className="flex gap-2 shrink-0">
                      <button onClick={() => respond(notif, 'confirmed')} disabled={responding === notif.notification_id || !isEligible}
                        className="flex items-center gap-1 bg-green-600 hover:bg-green-700 disabled:opacity-50 text-white text-xs font-medium px-3 py-1.5 rounded-lg">
                        {responding === notif.notification_id ? <Loader2 className="w-3 h-3 animate-spin" /> : <CheckCircle className="w-3 h-3" />}
                        Confirm
                      </button>
                      <button onClick={() => respond(notif, 'declined')} disabled={responding === notif.notification_id}
                        className="flex items-center gap-1 bg-white hover:bg-slate-100 border border-slate-200 text-slate-600 text-xs font-medium px-3 py-1.5 rounded-lg">
                        <XCircle className="w-3 h-3" /> Decline
                      </button>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Available compatible requests — donor can volunteer */}
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <div className="flex items-center gap-2 mb-4">
            <Heart className="w-5 h-5 text-red-600" />
            <h3 className="font-semibold text-slate-900">Available Blood Requests — Volunteer</h3>
            {availableRequests.length > 0 && (
              <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full">{availableRequests.length}</span>
            )}
          </div>

          {loading ? (
            <div className="text-center py-8 text-slate-400 text-sm">Loading…</div>
          ) : availableRequests.length === 0 ? (
            <div className="text-center py-10">
              <div className="w-12 h-12 bg-green-50 rounded-full flex items-center justify-center mx-auto mb-3">
                <CheckCircle className="w-6 h-6 text-green-400" />
              </div>
              <p className="text-slate-500 text-sm">No open requests for your blood group right now.</p>
              <p className="text-slate-400 text-xs mt-1">You'll be notified when a matching patient request comes in.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {availableRequests.map(req => (
                <RequestCard
                  key={req.request_id}
                  req={req}
                  donorBloodGroup={blood_group}
                  isEligible={isEligible}
                  volunteering={volunteering}
                  onVolunteer={volunteer}
                />
              ))}
            </div>
          )}
        </div>

        {/* Past responses */}
        {respondedNotifs.length > 0 && (
          <div className="bg-white rounded-2xl border border-slate-200 p-5">
            <h3 className="font-semibold text-slate-900 mb-3 text-sm">Your Donation History</h3>
            <div className="space-y-2">
              {respondedNotifs.slice(0, 5).map(notif => (
                <div key={notif.notification_id} className="flex items-center justify-between text-sm py-2 border-b border-slate-50 last:border-0">
                  <div className="flex items-center gap-2">
                    {notif.response === 'confirmed'
                      ? <CheckCircle className="w-4 h-4 text-green-500" />
                      : <XCircle className="w-4 h-4 text-slate-400" />
                    }
                    <span className="text-slate-700 text-xs">Request {notif.request_id?.slice(0, 8)}…</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${
                      notif.response === 'confirmed' ? 'bg-green-50 text-green-700'
                      : notif.response === 'declined' ? 'bg-slate-100 text-slate-500'
                      : 'bg-blue-50 text-blue-600'
                    }`}>{notif.response}</span>
                    <span className="text-xs text-slate-400">{notif.sent_at?.slice(0, 10)}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Consent toggle */}
        <div className="bg-white rounded-2xl border border-slate-200 p-5">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-slate-900 text-sm">Donation Consent</h3>
              <p className="text-xs text-slate-500 mt-0.5">Allow BloodBridge to contact you for donation requests</p>
            </div>
            <label className="relative inline-flex items-center cursor-pointer">
              <input type="checkbox" defaultChecked={profile?.consent_given !== false}
                onChange={async (e) => {
                  try { await updateConsent(user.user_id, e.target.checked) }
                  catch { /* silent */ }
                }}
                className="sr-only peer" />
              <div className="w-11 h-6 bg-slate-200 rounded-full peer peer-checked:bg-red-600 after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:after:translate-x-5" />
            </label>
          </div>
        </div>

        <div className="bg-slate-50 rounded-xl p-4 text-xs text-slate-500 border border-slate-200">
          <p className="font-medium text-slate-600 mb-1">Need help?</p>
          <p>Call our helpline: <span className="font-mono">1800-XXX-XXXX</span> (8 AM – 8 PM)</p>
          <p>Or chat with our assistant below to confirm, reschedule, or ask questions.</p>
        </div>
      </div>

      <DonorChatWidget donorId={user?.user_id} requestId="" notificationId="" />
    </div>
  )
}
