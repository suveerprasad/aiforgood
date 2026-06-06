import { useEffect, useState } from 'react'
import Navbar from '../components/layout/Navbar'
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer
} from 'recharts'
import {
  getAdminSummary, getDemandTrend, getFailureAnalysis,
  generateOutreachMessage, runGuestCampaign
} from '../services/api'
import { Sparkles, TrendingUp, AlertCircle, MessageSquare, Loader2, Users } from 'lucide-react'

const InsightCard = ({ icon: Icon, title, content, loading, color = 'text-slate-700' }) => (
  <div className="bg-white rounded-xl border border-slate-200 p-5">
    <div className="flex items-center gap-2 mb-3">
      <Icon className={`w-5 h-5 ${color}`} />
      <h3 className="font-semibold text-slate-900">{title}</h3>
    </div>
    {loading
      ? <div className="animate-pulse space-y-2">{[...Array(4)].map((_, i) => (
          <div key={i} className="h-3 bg-slate-100 rounded" style={{ width: `${70 + i * 7}%` }} />
        ))}</div>
      : <p className="text-sm text-slate-600 leading-relaxed whitespace-pre-line">{content || 'No data available'}</p>
    }
  </div>
)

export default function Insights() {
  const [summary, setSummary] = useState(null)
  const [trend, setTrend] = useState([])
  const [failureAnalysis, setFailureAnalysis] = useState('')
  const [loadingMain, setLoadingMain] = useState(true)
  const [loadingTrend, setLoadingTrend] = useState(true)
  const [loadingFailure, setLoadingFailure] = useState(false)

  // Outreach generator
  const [outreachForm, setOutreachForm] = useState({
    donor_name: '', patient_city: 'Hyderabad', blood_group: 'O Positive', collection_date: ''
  })
  const [generatedMsg, setGeneratedMsg] = useState('')
  const [generating, setGenerating] = useState(false)

  // Guest campaign
  const [campaignResult, setCampaignResult] = useState(null)
  const [runningCampaign, setRunningCampaign] = useState(false)

  useEffect(() => {
    getAdminSummary().then(r => setSummary(r.data)).finally(() => setLoadingMain(false))
    getDemandTrend().then(r => setTrend(r.data.trend || [])).finally(() => setLoadingTrend(false))
  }, [])

  const loadFailureAnalysis = async () => {
    setLoadingFailure(true)
    getFailureAnalysis().then(r => setFailureAnalysis(r.data.analysis)).finally(() => setLoadingFailure(false))
  }

  const generateMsg = async (e) => {
    e.preventDefault()
    setGenerating(true)
    try {
      const r = await generateOutreachMessage(outreachForm)
      setGeneratedMsg(r.data.message)
    } finally {
      setGenerating(false)
    }
  }

  const triggerCampaign = async (dryRun) => {
    setRunningCampaign(true)
    try {
      const r = await runGuestCampaign(dryRun)
      setCampaignResult(r.data)
    } finally {
      setRunningCampaign(false)
    }
  }

  return (
    <div className="flex-1 flex flex-col min-h-0">
      <Navbar title="AI Insights" subtitle="Bedrock-powered analytics and automation" />
      <div className="flex-1 overflow-y-auto p-6 space-y-6">

        {/* Admin summary */}
        <InsightCard
          icon={Sparkles}
          title="Weekly Operations Summary"
          content={summary?.ai_summary}
          loading={loadingMain}
          color="text-purple-600"
        />

        {/* Demand trend chart */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <div className="flex items-center gap-2 mb-4">
            <TrendingUp className="w-5 h-5 text-blue-600" />
            <h3 className="font-semibold text-slate-900">7-Day Demand Trend</h3>
          </div>
          {loadingTrend
            ? <div className="h-48 flex items-center justify-center text-slate-400 text-sm">Loading…</div>
            : (
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={trend}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                  <XAxis dataKey="date" tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                  <YAxis tick={{ fontSize: 11 }} tickLine={false} axisLine={false} />
                  <Tooltip />
                  <Line type="monotone" dataKey="units" stroke="#ef4444" strokeWidth={2} dot={{ fill: '#ef4444', r: 4 }} />
                </LineChart>
              </ResponsiveContainer>
            )
          }
        </div>

        {/* Demand stats */}
        {summary && (
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <p className="text-xs text-slate-500">Active Requests</p>
              <p className="text-2xl font-bold text-blue-700 mt-1">{summary.active_requests}</p>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <p className="text-xs text-slate-500">Units at Risk</p>
              <p className="text-2xl font-bold text-orange-700 mt-1">{summary.inventory_at_risk}</p>
            </div>
            <div className="bg-white rounded-xl border border-slate-200 p-4">
              <p className="text-xs text-slate-500">Top Demand</p>
              <p className="text-sm font-bold text-red-700 mt-1">
                {summary.demand_forecast
                  ? Object.entries(summary.demand_forecast).sort((a, b) => b[1] - a[1])[0]?.[0]
                  : '—'}
              </p>
            </div>
          </div>
        )}

        {/* Failure analysis */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <AlertCircle className="w-5 h-5 text-orange-600" />
              <h3 className="font-semibold text-slate-900">Failure Pattern Analysis</h3>
            </div>
            <button onClick={loadFailureAnalysis} disabled={loadingFailure}
              className="flex items-center gap-1.5 text-xs bg-orange-50 hover:bg-orange-100 text-orange-700 px-3 py-1.5 rounded-lg font-medium">
              {loadingFailure ? <Loader2 className="w-3 h-3 animate-spin" /> : <Sparkles className="w-3 h-3" />}
              Analyse Now
            </button>
          </div>
          {failureAnalysis
            ? <p className="text-sm text-slate-600 whitespace-pre-line leading-relaxed">{failureAnalysis}</p>
            : <p className="text-sm text-slate-400">Click "Analyse Now" to run Bedrock failure pattern analysis.</p>
          }
        </div>

        {/* Outreach message generator */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <div className="flex items-center gap-2 mb-4">
            <MessageSquare className="w-5 h-5 text-green-600" />
            <h3 className="font-semibold text-slate-900">Outreach Message Generator</h3>
          </div>
          <form onSubmit={generateMsg} className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Donor Name</label>
              <input required value={outreachForm.donor_name}
                onChange={e => setOutreachForm({ ...outreachForm, donor_name: e.target.value })}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-green-400"
                placeholder="e.g. Rahul" />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Patient City</label>
              <input value={outreachForm.patient_city}
                onChange={e => setOutreachForm({ ...outreachForm, patient_city: e.target.value })}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-green-400" />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Blood Group</label>
              <select value={outreachForm.blood_group}
                onChange={e => setOutreachForm({ ...outreachForm, blood_group: e.target.value })}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none">
                {['O Positive', 'O Negative', 'A Positive', 'A Negative', 'B Positive', 'B Negative', 'AB Positive', 'AB Negative'].map(bg =>
                  <option key={bg}>{bg}</option>
                )}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-600 mb-1">Collection Date</label>
              <input required type="date" value={outreachForm.collection_date}
                onChange={e => setOutreachForm({ ...outreachForm, collection_date: e.target.value })}
                className="w-full border border-slate-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-green-400" />
            </div>
            <div className="col-span-2 flex gap-3 items-start">
              <button type="submit" disabled={generating}
                className="flex items-center gap-2 bg-green-600 hover:bg-green-700 text-white text-sm font-medium px-4 py-2 rounded-lg">
                {generating ? <Loader2 className="w-4 h-4 animate-spin" /> : <Sparkles className="w-4 h-4" />}
                Generate Message
              </button>
              {generatedMsg && (
                <div className="flex-1 bg-green-50 border border-green-200 rounded-lg px-3 py-2 text-sm text-green-800">
                  {generatedMsg}
                </div>
              )}
            </div>
          </form>
        </div>

        {/* Guest campaign */}
        <div className="bg-white rounded-xl border border-slate-200 p-5">
          <div className="flex items-center gap-2 mb-3">
            <Users className="w-5 h-5 text-indigo-600" />
            <h3 className="font-semibold text-slate-900">Guest Activation Campaign</h3>
          </div>
          <p className="text-sm text-slate-500 mb-4">
            Target 2400+ registered guests whose blood groups match current high-demand types.
          </p>
          <div className="flex gap-3">
            <button onClick={() => triggerCampaign(true)} disabled={runningCampaign}
              className="flex items-center gap-2 text-sm border border-slate-200 hover:bg-slate-50 text-slate-600 px-4 py-2 rounded-lg">
              {runningCampaign && <Loader2 className="w-3 h-3 animate-spin" />}
              Dry Run
            </button>
            <button onClick={() => triggerCampaign(false)} disabled={runningCampaign}
              className="flex items-center gap-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium px-4 py-2 rounded-lg">
              {runningCampaign && <Loader2 className="w-4 h-4 animate-spin" />}
              Launch Campaign
            </button>
          </div>
          {campaignResult && (
            <div className="mt-3 bg-indigo-50 rounded-lg p-3 text-sm text-indigo-800">
              {campaignResult.dry_run ? '🔍 Dry Run: ' : '✅ Campaign sent: '}
              {campaignResult.activated} activated, {campaignResult.skipped} skipped.
              Target groups: {campaignResult.high_demand_groups?.join(', ')}
            </div>
          )}
        </div>

      </div>
    </div>
  )
}
