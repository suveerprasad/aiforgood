import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import Sidebar from './components/layout/Sidebar'
import Dashboard from './pages/Dashboard'
import Requests from './pages/Requests'
import Donors from './pages/Donors'
import Inventory from './pages/Inventory'
import Insights from './pages/Insights'
import Login from './pages/Login'
import Register from './pages/Register'
import DonorPortal from './pages/DonorPortal'
import PatientPortal from './pages/PatientPortal'

// Layout for Blood Bank Admin
function AdminLayout({ children }) {
  return (
    <div className="flex min-h-screen bg-slate-50">
      <Sidebar />
      <main className="flex-1 flex flex-col min-h-screen overflow-hidden">
        {children}
      </main>
    </div>
  )
}

// Route guard: redirect to login if not authenticated
function RequireAuth({ children, allowedRoles }) {
  const { user, loading } = useAuth()
  if (loading) return <div className="min-h-screen flex items-center justify-center text-slate-400">Loading…</div>
  if (!user) return <Navigate to="/login" replace />
  if (allowedRoles && !allowedRoles.includes(user.system_role)) {
    // Redirect to correct portal
    if (user.system_role === 'donor') return <Navigate to="/donor-portal" replace />
    if (user.system_role === 'patient') return <Navigate to="/patient-portal" replace />
    return <Navigate to="/" replace />
  }
  return children
}

// Redirect logged-in users away from login/register
function PublicOnly({ children }) {
  const { user, loading } = useAuth()
  if (loading) return null
  if (user) {
    if (user.system_role === 'donor') return <Navigate to="/donor-portal" replace />
    if (user.system_role === 'patient') return <Navigate to="/patient-portal" replace />
    return <Navigate to="/" replace />
  }
  return children
}

function AppRoutes() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<PublicOnly><Login /></PublicOnly>} />
      <Route path="/register" element={<PublicOnly><Register /></PublicOnly>} />

      {/* Donor portal */}
      <Route path="/donor-portal" element={
        <RequireAuth allowedRoles={['donor']}>
          <DonorPortal />
        </RequireAuth>
      } />

      {/* Patient portal */}
      <Route path="/patient-portal" element={
        <RequireAuth allowedRoles={['patient']}>
          <PatientPortal />
        </RequireAuth>
      } />

      {/* Admin / Blood Bank routes */}
      <Route path="/" element={
        <RequireAuth allowedRoles={['blood_bank']}>
          <AdminLayout><Dashboard /></AdminLayout>
        </RequireAuth>
      } />
      <Route path="/requests" element={
        <RequireAuth allowedRoles={['blood_bank']}>
          <AdminLayout><Requests /></AdminLayout>
        </RequireAuth>
      } />
      <Route path="/donors" element={
        <RequireAuth allowedRoles={['blood_bank']}>
          <AdminLayout><Donors /></AdminLayout>
        </RequireAuth>
      } />
      <Route path="/inventory" element={
        <RequireAuth allowedRoles={['blood_bank']}>
          <AdminLayout><Inventory /></AdminLayout>
        </RequireAuth>
      } />
      <Route path="/insights" element={
        <RequireAuth allowedRoles={['blood_bank']}>
          <AdminLayout><Insights /></AdminLayout>
        </RequireAuth>
      } />

      {/* Fallback */}
      <Route path="*" element={<Navigate to="/login" replace />} />
    </Routes>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  )
}
