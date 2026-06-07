import { useNavigate } from 'react-router-dom'
import { Bell, LogOut } from 'lucide-react'
import { useAuth } from '../../contexts/AuthContext'
import { useState } from 'react'

export default function Navbar({ title, subtitle }) {
  const { user, logout } = useAuth()
  const nav = useNavigate()
  const [showMenu, setShowMenu] = useState(false)

  const handleLogout = () => {
    logout()
    nav('/login')
  }

  const initials = (user?.name || 'A')
    .split(' ')
    .map(w => w[0])
    .slice(0, 2)
    .join('')
    .toUpperCase()

  return (
    <header className="h-16 bg-white border-b border-slate-200 flex items-center justify-between px-6 relative">
      <div>
        <h2 className="font-semibold text-slate-900">{title}</h2>
        {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
      </div>
      <div className="flex items-center gap-3">
        <button className="p-2 rounded-lg hover:bg-slate-100 text-slate-500 relative">
          <Bell className="w-4 h-4" />
        </button>
        <div className="relative">
          <button
            onClick={() => setShowMenu(m => !m)}
            className="flex items-center gap-2 hover:bg-slate-50 rounded-lg px-2 py-1 transition-colors"
          >
            <div className="w-8 h-8 rounded-full bg-red-600 flex items-center justify-center text-white text-xs font-bold">
              {initials}
            </div>
            {user && (
              <div className="text-left hidden sm:block">
                <p className="text-xs font-medium text-slate-800 leading-tight">{user.name}</p>
                <p className="text-xs text-slate-400 capitalize leading-tight">{user.system_role?.replace('_', ' ')}</p>
              </div>
            )}
          </button>
          {showMenu && (
            <div className="absolute right-0 top-10 bg-white border border-slate-200 rounded-xl shadow-lg w-48 py-1 z-50">
              {user && (
                <div className="px-4 py-2 border-b border-slate-100">
                  <p className="text-xs font-medium text-slate-800">{user.name}</p>
                  <p className="text-xs text-slate-500 truncate">{user.email}</p>
                </div>
              )}
              <button
                onClick={handleLogout}
                className="flex items-center gap-2 w-full text-left px-4 py-2 text-sm text-red-600 hover:bg-red-50 transition-colors"
              >
                <LogOut className="w-4 h-4" />
                Sign Out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
