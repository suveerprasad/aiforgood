import { createContext, useContext, useState, useEffect } from 'react'
import { loginUser, registerUser, getMe } from '../services/api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)       // { user_id, name, email, system_role, blood_group }
  const [loading, setLoading] = useState(true)

  // Rehydrate from localStorage on mount
  useEffect(() => {
    const token = localStorage.getItem('bb_token')
    const stored = localStorage.getItem('bb_user')
    if (token && stored) {
      try {
        setUser(JSON.parse(stored))
      } catch {
        localStorage.removeItem('bb_token')
        localStorage.removeItem('bb_user')
      }
    }
    setLoading(false)
  }, [])

  const login = async (email, password) => {
    const res = await loginUser(email, password)
    const data = res.data
    localStorage.setItem('bb_token', data.access_token)
    localStorage.setItem('bb_user', JSON.stringify(data))
    setUser(data)
    return data
  }

  const register = async (formData) => {
    const res = await registerUser(formData)
    const data = res.data
    localStorage.setItem('bb_token', data.access_token)
    localStorage.setItem('bb_user', JSON.stringify(data))
    setUser(data)
    return data
  }

  const logout = () => {
    localStorage.removeItem('bb_token')
    localStorage.removeItem('bb_user')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used inside AuthProvider')
  return ctx
}
