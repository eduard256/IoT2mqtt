import { ReactNode } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { 
  Home, 
  Cpu, 
  Box, 
  Activity,
  Network,
  LogOut,
  Moon,
  Sun,
  Languages,
  Menu,
  X
} from 'lucide-react'
import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useAuthStore } from '@/stores/authStore'
import { useThemeStore } from '@/stores/themeStore'
import { cn } from '@/lib/utils'

interface LayoutProps {
  children: ReactNode
}

export default function Layout({ children }: LayoutProps) {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const logout = useAuthStore(state => state.logout)
  const { theme, setTheme } = useThemeStore()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  
  const menuItems = [
    { path: '/', icon: Home, label: t('dashboard.title') },
    { path: '/integrations', icon: Box, label: t('integrations.title') },
    { path: '/devices', icon: Cpu, label: t('devices.title') },
    { path: '/mqtt', icon: Network, label: t('mqtt_explorer.title') },
    { path: '/containers', icon: Activity, label: t('containers.title') },
  ]
  
  const handleLogout = () => {
    logout()
    navigate('/auth')
  }
  
  const toggleTheme = () => {
    const newTheme = theme === 'dark' ? 'light' : 'dark'
    setTheme(newTheme)
  }
  
  return (
    <div className="min-h-screen bg-background">
      {/* Mobile menu button */}
      <button
        onClick={() => setSidebarOpen(!sidebarOpen)}
        className="lg:hidden fixed top-4 left-4 z-50 p-2 rounded-lg bg-card shadow-lg"
      >
        {sidebarOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
      </button>
      
      {/* Sidebar */}
      <AnimatePresence>
        {(sidebarOpen || window.innerWidth >= 1024) && (
          <motion.aside
            initial={{ x: -280 }}
            animate={{ x: 0 }}
            exit={{ x: -280 }}
            transition={{ type: 'spring', damping: 25, stiffness: 200 }}
            className={cn(
              "fixed left-0 top-0 h-full w-64 bg-card border-r z-40",
              "lg:translate-x-0"
            )}
          >
            <div className="flex flex-col h-full">
              {/* Logo */}
              <div className="p-6 border-b">
                <h1 className="text-2xl font-bold gradient-text">IoT2MQTT</h1>
              </div>
              
              {/* Navigation */}
              <nav className="flex-1 p-4 space-y-1">
                {menuItems.map(item => (
                  <NavLink
                    key={item.path}
                    to={item.path}
                    onClick={() => setSidebarOpen(false)}
                    className={({ isActive }) => cn(
                      "flex items-center space-x-3 px-3 py-2 rounded-lg transition-all",
                      isActive 
                        ? "bg-primary text-primary-foreground shadow-sm" 
                        : "hover:bg-accent"
                    )}
                  >
                    <item.icon className="h-5 w-5" />
                    <span>{item.label}</span>
                  </NavLink>
                ))}
              </nav>
              
              {/* Bottom actions */}
              <div className="p-4 border-t space-y-2">
                {/* Language selector */}
                <div className="flex items-center space-x-2 px-3 py-2">
                  <Languages className="h-5 w-5 text-muted-foreground" />
                  <select
                    value={i18n.language}
                    onChange={(e) => i18n.changeLanguage(e.target.value)}
                    className="bg-transparent outline-none text-sm flex-1"
                  >
                    <option value="en">English</option>
                    <option value="ru">Русский</option>
                    <option value="zh">中文</option>
                  </select>
                </div>
                
                {/* Theme toggle */}
                <button
                  onClick={toggleTheme}
                  className="flex items-center space-x-3 px-3 py-2 rounded-lg hover:bg-accent w-full"
                >
                  {theme === 'dark' ? (
                    <Sun className="h-5 w-5" />
                  ) : (
                    <Moon className="h-5 w-5" />
                  )}
                  <span className="text-sm">{t('settings.theme')}</span>
                </button>
                
                {/* Logout */}
                <button
                  onClick={handleLogout}
                  className="flex items-center space-x-3 px-3 py-2 rounded-lg hover:bg-accent w-full text-red-600 dark:text-red-400"
                >
                  <LogOut className="h-5 w-5" />
                  <span className="text-sm">Logout</span>
                </button>
              </div>
            </div>
          </motion.aside>
        )}
      </AnimatePresence>
      
      {/* Backdrop for mobile */}
      {sidebarOpen && (
        <div
          className="lg:hidden fixed inset-0 bg-black/50 z-30"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      
      {/* Main content */}
      <main className={cn(
        "min-h-screen transition-all duration-300",
        "lg:pl-64"
      )}>
        <div className="p-6 lg:p-8">
          {children}
        </div>
      </main>
    </div>
  )
}