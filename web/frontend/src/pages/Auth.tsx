import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import { Loader2, Key } from 'lucide-react'
import toast from 'react-hot-toast'
import axios from 'axios'

import { useAuthStore } from '@/stores/authStore'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent } from '@/components/ui/card'

export default function Auth() {
  const { t, i18n } = useTranslation()
  const navigate = useNavigate()
  const login = useAuthStore(state => state.login)
  const checkAuth = useAuthStore(state => state.checkAuth)
  
  const [key, setKey] = useState('')
  const [loading, setLoading] = useState(false)
  const [checkingSetup, setCheckingSetup] = useState(true)
  const [isFirstTime, setIsFirstTime] = useState(false)
  
  useEffect(() => {
    // Check if already authenticated
    checkAuth().then(isAuth => {
      if (isAuth) {
        checkSetupAndRedirect()
      } else {
        checkFirstTimeSetup()
      }
    })
  }, [])
  
  const checkFirstTimeSetup = async () => {
    try {
      const response = await axios.get('/api/setup/status')
      setIsFirstTime(!response.data.has_access_key)
      setCheckingSetup(false)
    } catch {
      setCheckingSetup(false)
    }
  }
  
  const checkSetupAndRedirect = async () => {
    try {
      const response = await axios.get('/api/setup/status')
      if (!response.data.has_mqtt_config) {
        navigate('/setup')
      } else {
        navigate('/')
      }
    } catch {
      navigate('/')
    }
  }
  
  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!key.trim()) return
    
    setLoading(true)
    
    const success = await login(key)
    
    if (success) {
      toast.success(t('common.success'))
      checkSetupAndRedirect()
    } else {
      toast.error(t('auth.invalid_key'))
      setLoading(false)
    }
  }
  
  if (checkingSetup) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }
  
  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-950">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-md"
      >
        <div className="text-center mb-8">
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.2, type: "spring", stiffness: 200 }}
            className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-primary/10 mb-4"
          >
            <Key className="h-10 w-10 text-primary" />
          </motion.div>
          
          <h1 className="text-3xl font-bold gradient-text mb-2">
            {t('auth.title')}
          </h1>
          <p className="text-muted-foreground">
            {t('auth.subtitle')}
          </p>
          
          {isFirstTime && (
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.5 }}
              className="text-sm text-blue-600 dark:text-blue-400 mt-2"
            >
              {t('auth.first_time')}
            </motion.p>
          )}
        </div>
        
        <Card className="backdrop-blur-lg bg-card/50">
          <CardContent className="p-6">
            <form onSubmit={handleLogin} className="space-y-4">
              <div className="space-y-2">
                <Input
                  type="password"
                  placeholder={t('auth.access_key')}
                  value={key}
                  onChange={(e) => setKey(e.target.value)}
                  disabled={loading}
                  className="h-12 text-center text-lg tracking-wider"
                  autoFocus
                />
              </div>
              
              <Button
                type="submit"
                className="w-full h-12 text-lg"
                disabled={loading || !key.trim()}
              >
                {loading ? (
                  <>
                    <Loader2 className="mr-2 h-5 w-5 animate-spin" />
                    {t('common.loading')}
                  </>
                ) : (
                  t('auth.login')
                )}
              </Button>
            </form>
          </CardContent>
        </Card>
        
        <div className="mt-8 text-center">
          <div className="flex items-center justify-center space-x-4 text-sm text-muted-foreground">
            <button
              onClick={() => {
                document.documentElement.classList.toggle('dark')
              }}
              className="hover:text-foreground transition-colors"
            >
              🌙 / ☀️
            </button>
            <span>•</span>
            <select
              onChange={(e) => i18n.changeLanguage(e.target.value)}
              className="bg-transparent outline-none hover:text-foreground transition-colors cursor-pointer"
              value={i18n.language}
            >
              <option value="en">English</option>
              <option value="ru">Русский</option>
              <option value="zh">中文</option>
            </select>
          </div>
        </div>
      </motion.div>
    </div>
  )
}