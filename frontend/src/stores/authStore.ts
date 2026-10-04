import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { AuthState } from '@/types/auth'

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      token: null,
      user: null,
      isAuthenticated: false,
      login: (token, username, role) =>
        set({
          token,
          user: { username, role: role as 'admin' | 'user' },
          isAuthenticated: true,
        }),
      logout: () =>
        set({
          token: null,
          user: null,
          isAuthenticated: false,
        }),
    }),
    { name: 'copilot-auth' }
  )
)
