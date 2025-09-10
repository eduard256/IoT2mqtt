import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import axios from 'axios'

interface AuthState {
  token: string | null
  isAuthenticated: boolean
  login: (key: string) => Promise<boolean>
  logout: () => void
  checkAuth: () => Promise<boolean>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      token: null,
      isAuthenticated: false,
      
      login: async (key: string) => {
        try {
          const response = await axios.post('/api/auth/login', { key })
          const { token } = response.data
          
          // Set default auth header
          axios.defaults.headers.common['Authorization'] = `Bearer ${token}`
          
          set({ token, isAuthenticated: true })
          return true
        } catch (error) {
          set({ token: null, isAuthenticated: false })
          return false
        }
      },
      
      logout: () => {
        delete axios.defaults.headers.common['Authorization']
        set({ token: null, isAuthenticated: false })
      },
      
      checkAuth: async () => {
        const token = get().token
        if (!token) return false
        
        try {
          axios.defaults.headers.common['Authorization'] = `Bearer ${token}`
          await axios.get('/api/auth/check')
          set({ isAuthenticated: true })
          return true
        } catch {
          get().logout()
          return false
        }
      },
    }),
    {
      name: 'auth-storage',
    }
  )
)