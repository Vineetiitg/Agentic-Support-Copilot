import { type ReactNode } from 'react'
import { MessageSquare, Shield, LogOut, Plus } from 'lucide-react'
import { useNavigate, useLocation } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { useAuthStore } from '@/stores/authStore'
import SessionList from '@/components/sidebar/SessionList'

interface AppLayoutProps {
  children: ReactNode
  onNewChat?: () => void
  activeSessionId?: string
  onSelectSession?: (sessionId: string, messages: any[]) => void
}

export default function AppLayout({ children, onNewChat, activeSessionId, onSelectSession }: AppLayoutProps) {
  const { user, logout, isAuthenticated } = useAuthStore()
  const navigate = useNavigate()
  const location = useLocation()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="flex h-screen">
      {/* Sidebar */}
      <aside className="w-64 flex-shrink-0 bg-slate-900/50 border-r border-white/5 flex flex-col">
        {/* Logo */}
        <div className="p-4 border-b border-white/5">
          <h1 className="text-lg font-bold bg-gradient-to-r from-blue-400 via-purple-400 to-pink-400 bg-clip-text text-transparent">
            🚀 Support Copilot
          </h1>
        </div>

        {/* New chat button */}
        <div className="p-3">
          <Button variant="outline" className="w-full justify-start gap-2" onClick={onNewChat}>
            <Plus size={16} /> New Chat
          </Button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 p-3 space-y-1 overflow-y-auto">
          <Button
            variant={location.pathname === '/' ? 'default' : 'ghost'}
            className="w-full justify-start gap-2"
            onClick={() => navigate('/')}
          >
            <MessageSquare size={16} /> Chat
          </Button>
          {user?.role === 'admin' && (
            <Button
              variant={location.pathname === '/admin' ? 'default' : 'ghost'}
              className="w-full justify-start gap-2"
              onClick={() => navigate('/admin')}
            >
              <Shield size={16} /> Admin
            </Button>
          )}

          {/* Session List */}
          {activeSessionId !== undefined && onSelectSession && (
            <div className="pt-4 mt-4 border-t border-white/5">
              <h3 className="px-2 text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">
                Recent Chats
              </h3>
              <SessionList
                activeSessionId={activeSessionId}
                onSelectSession={onSelectSession}
              />
            </div>
          )}
        </nav>

        {/* User section */}
        <div className="p-3 border-t border-white/5">
          {isAuthenticated && user ? (
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-200">{user.username}</p>
                <p className="text-xs text-slate-500 capitalize">{user.role}</p>
              </div>
              <Button variant="ghost" size="icon" onClick={handleLogout} title="Logout">
                <LogOut size={16} />
              </Button>
            </div>
          ) : (
            <Button variant="outline" className="w-full" onClick={() => navigate('/login')}>
              Sign In
            </Button>
          )}
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {children}
      </main>
    </div>
  )
}
