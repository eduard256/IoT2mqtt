import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useTranslation } from 'react-i18next'
import { motion } from 'framer-motion'
import { Loader2, Wifi, Check, X } from 'lucide-react'
import toast from 'react-hot-toast'
import axios from 'axios'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card'

export default function Setup() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  
  const [config, setConfig] = useState({
    host: 'localhost',
    port: 1883,
    username: '',
    password: '',
    base_topic: 'IoT2mqtt',
    client_prefix: 'iot2mqtt',
    qos: 1,
    retain: true,
    keepalive: 60
  })
  
  const [testing, setTesting] = useState(false)
  const [saving, setSaving] = useState(false)
  const [testResult, setTestResult] = useState<boolean | null>(null)
  
  const handleTest = async () => {
    setTesting(true)
    setTestResult(null)
    
    try {
      const response = await axios.post('/api/mqtt/test', config)
      setTestResult(response.data.success)
      
      if (response.data.success) {
        toast.success(t('setup.mqtt.connection_success'))
      } else {
        toast.error(response.data.message || t('setup.mqtt.connection_failed'))
      }
    } catch (error) {
      setTestResult(false)
      toast.error(t('setup.mqtt.connection_failed'))
    } finally {
      setTesting(false)
    }
  }
  
  const handleSave = async () => {
    setSaving(true)
    
    try {
      const response = await axios.post('/api/mqtt/config', config)
      
      if (response.data.success) {
        toast.success(t('common.success'))
        navigate('/')
      } else {
        toast.error(response.data.message || t('common.error'))
      }
    } catch (error) {
      toast.error(t('common.error'))
    } finally {
      setSaving(false)
    }
  }
  
  return (
    <div className="min-h-screen flex items-center justify-center p-4 bg-gradient-to-br from-gray-50 to-gray-100 dark:from-gray-900 dark:to-gray-950">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5 }}
        className="w-full max-w-2xl"
      >
        <div className="text-center mb-8">
          <motion.div
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            transition={{ delay: 0.2, type: "spring", stiffness: 200 }}
            className="inline-flex items-center justify-center w-20 h-20 rounded-full bg-primary/10 mb-4"
          >
            <Wifi className="h-10 w-10 text-primary" />
          </motion.div>
          
          <h1 className="text-3xl font-bold gradient-text mb-2">
            {t('setup.mqtt.title')}
          </h1>
          <p className="text-muted-foreground">
            {t('setup.mqtt.description')}
          </p>
        </div>
        
        <Card>
          <CardHeader>
            <CardTitle>{t('setup.mqtt.broker_settings')}</CardTitle>
            <CardDescription>
              {t('setup.mqtt.description')}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Connection Settings */}
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">
                  {t('setup.mqtt.host')}
                </label>
                <Input
                  value={config.host}
                  onChange={(e) => setConfig({ ...config, host: e.target.value })}
                  placeholder="localhost"
                />
              </div>
              
              <div className="space-y-2">
                <label className="text-sm font-medium">
                  {t('setup.mqtt.port')}
                </label>
                <Input
                  type="number"
                  value={config.port}
                  onChange={(e) => setConfig({ ...config, port: parseInt(e.target.value) })}
                  placeholder="1883"
                />
              </div>
            </div>
            
            {/* Authentication */}
            <div className="space-y-4">
              <h3 className="text-sm font-semibold">{t('setup.mqtt.authentication_optional')}</h3>
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">
                    {t('setup.mqtt.username')}
                  </label>
                  <Input
                    value={config.username}
                    onChange={(e) => setConfig({ ...config, username: e.target.value })}
                    placeholder="mqtt_user"
                  />
                </div>
                
                <div className="space-y-2">
                  <label className="text-sm font-medium">
                    {t('setup.mqtt.password')}
                  </label>
                  <Input
                    type="password"
                    value={config.password}
                    onChange={(e) => setConfig({ ...config, password: e.target.value })}
                    placeholder="••••••••"
                  />
                </div>
              </div>
            </div>
            
            {/* Topics */}
            <div className="space-y-2">
              <label className="text-sm font-medium">
                {t('setup.mqtt.base_topic')}
              </label>
              <Input
                value={config.base_topic}
                onChange={(e) => setConfig({ ...config, base_topic: e.target.value })}
                placeholder="IoT2mqtt"
              />
              <p className="text-xs text-muted-foreground">
                {t('setup.mqtt.topics_format', { format: `${config.base_topic}/v1/instances/...` })}
              </p>
            </div>
            
            {/* Test Result */}
            {testResult !== null && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                className={`p-4 rounded-lg flex items-center space-x-2 ${
                  testResult 
                    ? 'bg-green-50 dark:bg-green-900/20 text-green-600 dark:text-green-400' 
                    : 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400'
                }`}
              >
                {testResult ? (
                  <>
                    <Check className="h-5 w-5" />
                    <span>{t('setup.mqtt.connection_success')}</span>
                  </>
                ) : (
                  <>
                    <X className="h-5 w-5" />
                    <span>{t('setup.mqtt.connection_failed')}</span>
                  </>
                )}
              </motion.div>
            )}
            
            {/* Actions */}
            <div className="flex justify-between pt-4">
              <Button
                variant="outline"
                onClick={handleTest}
                disabled={testing || saving}
              >
                {testing ? (
                  <>
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    {t('setup.mqtt.testing')}
                  </>
                ) : (
                  t('setup.mqtt.test_connection')
                )}
              </Button>
              
              <div className="space-x-2">
                <Button
                  variant="outline"
                  onClick={() => navigate('/')}
                  disabled={saving}
                >
                  {t('common.cancel')}
                </Button>
                
                <Button
                  onClick={handleSave}
                  disabled={saving || testResult === false}
                >
                  {saving ? (
                    <>
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                      {t('common.loading')}
                    </>
                  ) : (
                    t('common.save')
                  )}
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </motion.div>
    </div>
  )
}