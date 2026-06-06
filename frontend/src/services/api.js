import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || '/api/v1'

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    console.error('API Error:', err.response?.data || err.message)
    return Promise.reject(err)
  }
)

// ─── Patients / Requests ────────────────────────────────────────────────────
export const createRequest = (data) => api.post('/patients/requests', data)
export const getRequest = (id) => api.get(`/patients/requests/${id}`)
export const listRequests = (params) => api.get('/patients/requests', { params })
export const updateRequest = (id, data) => api.patch(`/patients/requests/${id}`, data)

// ─── Donors ─────────────────────────────────────────────────────────────────
export const listDonors = (params) => api.get('/donors', { params })
export const getDonor = (id) => api.get(`/donors/${id}`)
export const updateConsent = (id, consent) => api.patch(`/donors/${id}/consent`, { consent_given: consent })
export const getDonorsByBridge = (bridgeId) => api.get(`/donors/by-bridge/${bridgeId}`)

// ─── Matching ────────────────────────────────────────────────────────────────
export const triggerMatching = (data) => api.post('/matching/match', data)
export const getDemandForecast = (daysAhead = 7) => api.get('/matching/demand-forecast', { params: { days_ahead: daysAhead } })
export const getUrgencyQueue = (daysAhead = 14) => api.get('/matching/urgency-queue', { params: { days_ahead: daysAhead } })

// ─── Inventory ───────────────────────────────────────────────────────────────
export const getInventorySummary = () => api.get('/inventory/summary')
export const checkInventory = (bloodGroup, units) => api.get('/inventory/check', { params: { blood_group: bloodGroup, units } })
export const getExpiryAlerts = () => api.get('/inventory/expiry-alerts')
export const addBloodUnit = (data) => api.post('/inventory/units', data)
export const issueBloodUnits = (requestId) => api.post(`/inventory/requests/${requestId}/issue`)
export const releaseBloodUnits = (requestId) => api.post(`/inventory/requests/${requestId}/release`)

// ─── Insights ────────────────────────────────────────────────────────────────
export const getAdminSummary = () => api.get('/insights/admin-summary')
export const getDemandTrend = () => api.get('/insights/demand-trend')
export const getFailureAnalysis = () => api.get('/insights/failure-analysis')
export const generateOutreachMessage = (data) => api.post('/insights/outreach-message', data)
export const runGuestCampaign = (dryRun = false) => api.post('/insights/guest-campaign', null, { params: { dry_run: dryRun } })

// ─── Webhooks ────────────────────────────────────────────────────────────────
export const recordDonorResponse = (data) => api.post('/webhooks/donor-response', data)

export default api
