export interface User {
  username: string
  role: 'admin' | 'user' | 'guest'
}

export interface LoginResponse {
  access_token: string
  token_type: string
  role: string
}

export interface AuthState {
  token: string | null
  user: User | null
  isAuthenticated: boolean
  login: (token: string, username: string, role: string) => void
  logout: () => void
}
