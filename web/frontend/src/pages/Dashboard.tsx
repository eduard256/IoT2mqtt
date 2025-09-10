import { useTranslation } from 'react-i18next'
import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'
import {
  Wifi,
  WifiOff,
  Box,
  Cpu,
  Activity,
  Plus,
  ArrowUp,
  ArrowDown
} from 'lucide-react'
import axios from 'axios'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { useNavigate } from 'react-router-dom'
import { cn } from '@/lib/utils'

interface SystemStatus {
  mqtt_connected: boolean
  docker_available: boolean
  instances_count: number
  devices_count: number
  containers_running: number
  containers_total: number
}

interface ConnectorInfo {
  name: string
  display_name: string
  instances: string[]
  has_icon: boolean
}

export default function Dashboard() {
  const { t } = useTranslation()
  const navigate = useNavigate()
  
  // Fetch system status
  const { data: status } = useQuery({
    queryKey: ['system-status'],
    queryFn: async () => {
      const response = await axios.get<SystemStatus>('/api/system/status')
      return response.data
    },
    refetchInterval: 5000
  })
  
  // Fetch connectors
  const { data: connectors = [] } = useQuery({
    queryKey: ['connectors'],
    queryFn: async () => {
      const response = await axios.get<ConnectorInfo[]>('/api/connectors')
      return response.data
    }
  })
  
  const statsCards = [
    {
      title: t('dashboard.mqtt_status'),
      value: status?.mqtt_connected ? t('common.connected') : t('common.disconnected'),
      icon: status?.mqtt_connected ? Wifi : WifiOff,
      color: status?.mqtt_connected ? 'text-green-500' : 'text-red-500',
      trend: status?.mqtt_connected ? 'up' : 'down'
    },
    {
      title: t('dashboard.integrations'),
      value: status?.instances_count || 0,
      icon: Box,
      color: 'text-blue-500',
      trend: 'stable'
    },
    {
      title: t('dashboard.total_devices'),
      value: status?.devices_count || 0,
      icon: Cpu,
      color: 'text-purple-500',
      trend: 'up'
    },
    {
      title: t('dashboard.containers_running'),
      value: `${status?.containers_running || 0} / ${status?.containers_total || 0}`,
      icon: Activity,
      color: 'text-orange-500',
      trend: 'stable'
    }
  ]
  
  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold">{t('dashboard.title')}</h1>
          <p className="text-muted-foreground mt-1">
            Welcome to your smart home control center
          </p>
        </div>
        
        <Button
          onClick={() => navigate('/integrations')}
          className="shadow-lg"
        >
          <Plus className="mr-2 h-4 w-4" />
          {t('dashboard.add_integration')}
        </Button>
      </div>
      
      {/* Stats Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        {statsCards.map((stat, index) => (
          <motion.div
            key={stat.title}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.1 }}
          >
            <Card className="hover:shadow-lg transition-all duration-300 relative overflow-hidden">
              <div className="absolute top-0 right-0 p-4 opacity-10">
                <stat.icon className="h-24 w-24" />
              </div>
              
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  {stat.title}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-baseline space-x-2">
                  <span className={cn("text-2xl font-bold", stat.color)}>
                    {stat.value}
                  </span>
                  {stat.trend === 'up' && (
                    <ArrowUp className="h-4 w-4 text-green-500" />
                  )}
                  {stat.trend === 'down' && (
                    <ArrowDown className="h-4 w-4 text-red-500" />
                  )}
                </div>
              </CardContent>
            </Card>
          </motion.div>
        ))}
      </div>
      
      {/* Active Integrations */}
      <div>
        <h2 className="text-xl font-semibold mb-4">{t('dashboard.integrations')}</h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          {connectors.filter(c => c.instances.length > 0).map((connector, index) => (
            <motion.div
              key={connector.name}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: index * 0.05 }}
            >
              <Card 
                className="hover:shadow-lg transition-all duration-300 cursor-pointer"
                onClick={() => navigate('/integrations')}
              >
                <CardContent className="p-6">
                  <div className="flex items-center space-x-4">
                    <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center">
                      <Box className="h-6 w-6 text-primary" />
                    </div>
                    <div className="flex-1">
                      <h3 className="font-semibold">{connector.display_name}</h3>
                      <p className="text-sm text-muted-foreground">
                        {connector.instances.length} {connector.instances.length === 1 ? 'instance' : 'instances'}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            </motion.div>
          ))}
          
          {/* Add new integration card */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: connectors.length * 0.05 }}
          >
            <Card 
              className="hover:shadow-lg transition-all duration-300 cursor-pointer border-dashed"
              onClick={() => navigate('/integrations')}
            >
              <CardContent className="p-6">
                <div className="flex items-center space-x-4">
                  <div className="w-12 h-12 rounded-lg bg-muted flex items-center justify-center">
                    <Plus className="h-6 w-6 text-muted-foreground" />
                  </div>
                  <div className="flex-1">
                    <h3 className="font-semibold text-muted-foreground">
                      {t('integrations.add_new')}
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      Configure new devices
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </motion.div>
        </div>
      </div>
    </div>
  )
}