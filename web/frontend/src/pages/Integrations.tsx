import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import { getAuthToken } from '@/utils/auth'
import { Search, Plus, Loader2, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { toast } from '@/hooks/use-toast'
import IntegrationCard from '@/components/integrations/IntegrationCard'
import DiscoveredDeviceCard from '@/components/integrations/DiscoveredDeviceCard'
import AddIntegrationModal from '@/components/integrations/AddIntegrationModal'
import IntegrationInstancesPage from '@/components/integrations/IntegrationInstancesPage'

interface DiscoveredDevice {
  id: string
  name: string
  integration: string
  ip?: string
  port?: number
  model?: string
  manufacturer?: string
  capabilities?: Record<string, any>
  discovered_at: string
  added?: boolean
}

interface ConfiguredIntegration {
  name: string
  display_name: string
  instances_count: number
  status: 'connected' | 'error' | 'offline' | 'configuring'
  last_seen?: string
}

export default function Integrations() {
  const { t } = useTranslation()
  const [loading, setLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [discoveredDevices, setDiscoveredDevices] = useState<DiscoveredDevice[]>([])
  const [configuredIntegrations, setConfiguredIntegrations] = useState<ConfiguredIntegration[]>([])
  const [showAddModal, setShowAddModal] = useState(false)
  const [selectedIntegration, setSelectedIntegration] = useState<string | null>(null)
  const wsRef = useRef<WebSocket | null>(null)

  // Initialize WebSocket for real-time discovery updates
  useEffect(() => {
    const token = getAuthToken()
    if (!token) return

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const wsUrl = `${protocol}://${window.location.host}/api/discovery/ws`
    const ws = new WebSocket(wsUrl)
    
    ws.onopen = () => {
      console.log('Discovery WebSocket connected')
    }

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)
        if (data.devices) {
          setDiscoveredDevices(data.devices.filter((d: DiscoveredDevice) => !d.added))
        }
      } catch (error) {
        console.error('WebSocket message error:', error)
      }
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }

    ws.onclose = () => {
      console.log('Discovery WebSocket disconnected')
      // Reconnect after 5 seconds
      setTimeout(() => {
        if (wsRef.current === ws) {
          initializeWebSocket()
        }
      }, 5000)
    }

    wsRef.current = ws

    return () => {
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
    }
  }, [])

  const initializeWebSocket = () => {
    const token = getAuthToken()
    if (!token) return

    const protocol = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const wsUrl = `${protocol}://${window.location.host}/api/discovery/ws`
    const ws = new WebSocket(wsUrl)
    wsRef.current = ws
  }

  // Fetch initial data
  useEffect(() => {
    fetchData()
  }, [])

  const fetchData = async () => {
    try {
      const token = getAuthToken()
      if (!token) {
        throw new Error('No authentication token')
      }

      // Fetch discovered devices (only non-added ones)
      const devicesResponse = await fetch('/api/discovery/devices', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (devicesResponse.ok) {
        const devices = await devicesResponse.json()
        setDiscoveredDevices(devices.filter((d: DiscoveredDevice) => !d.added))
      }

      // Fetch configured integrations
      const integrationsResponse = await fetch('/api/integrations/', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (integrationsResponse.ok) {
        const integrations = await integrationsResponse.json()
        setConfiguredIntegrations(integrations)
      }

    } catch (error) {
      toast({
        title: t('common.error'),
        description: t('common.failed_to_load_data'),
        variant: 'destructive'
      })
    } finally {
      setLoading(false)
    }
  }

  const handleAddDevice = async (device: DiscoveredDevice) => {
    const instanceId = prompt(t('integrations.enter_instance_id'))
    if (!instanceId) return

    const friendlyName = prompt(t('integrations.enter_friendly_name'), device.name)
    if (!friendlyName) return

    try {
      const token = getAuthToken()
      const response = await fetch(`/api/discovery/devices/${device.id}/add`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          device_id: device.id,
          instance_id: instanceId,
          friendly_name: friendlyName
        })
      })

      if (response.ok) {
        toast({
          title: t('integrations.device_added'),
          description: t('integrations.device_added_success')
        })
        fetchData() // Refresh data
      } else {
        throw new Error('Failed to add device')
      }
    } catch (error) {
      toast({
        title: t('common.error'),
        description: t('integrations.failed_to_add_device'),
        variant: 'destructive'
      })
    }
  }

  const handleIgnoreDevice = async (deviceId: string) => {
    try {
      const token = getAuthToken()
      const response = await fetch(`/api/discovery/devices/${deviceId}`, {
        method: 'DELETE',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (response.ok) {
        toast({
          title: t('integrations.device_ignored'),
          description: t('integrations.device_removed_from_list')
        })
        fetchData()
      }
    } catch (error) {
      toast({
        title: t('common.error'),
        description: t('integrations.failed_to_ignore_device'),
        variant: 'destructive'
      })
    }
  }

  const handleIntegrationClick = (integration: ConfiguredIntegration) => {
    setSelectedIntegration(integration.name)
  }

  // Filter configured integrations based on search
  const filteredIntegrations = configuredIntegrations.filter(integration =>
    integration.display_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    integration.name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  // Show integration instances page if integration is selected
  if (selectedIntegration) {
    return (
      <IntegrationInstancesPage
        integrationName={selectedIntegration}
        onBack={() => setSelectedIntegration(null)}
      />
    )
  }

  return (
    <div className="space-y-6">
      {/* Header with Search */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold">{t('integrations.title')}</h1>
          <p className="text-muted-foreground mt-1">
            {t('integrations.manage_description')}
          </p>
        </div>
      </div>

      {/* Search Bar */}
      <div className="relative max-w-md">
        <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-muted-foreground h-4 w-4" />
        <Input
          type="text"
          placeholder={t('integrations.search_configured')}
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="pl-10"
        />
      </div>

      {/* Discovered Devices Section */}
      {discoveredDevices.length > 0 && (
        <div className="space-y-4">
          <h2 className="text-xl font-semibold">{t('integrations.discovered')}</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {discoveredDevices.map((device) => (
              <DiscoveredDeviceCard
                key={device.id}
                device={device}
                onAdd={handleAddDevice}
                onIgnore={handleIgnoreDevice}
              />
            ))}
          </div>
        </div>
      )}

      {/* Configured Integrations Section */}
      <div className="space-y-4">
        <h2 className="text-xl font-semibold">{t('integrations.configured')}</h2>

        {filteredIntegrations.length === 0 ? (
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              {searchQuery
                ? t('integrations.no_match')
                : t('integrations.no_configured_yet')}
            </AlertDescription>
          </Alert>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredIntegrations.map((integration) => (
              <IntegrationCard
                key={integration.name}
                integration={integration}
                onClick={() => handleIntegrationClick(integration)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Floating Action Button */}
      <Button
        className="fixed bottom-6 right-6 h-14 w-14 rounded-full shadow-lg hover:shadow-xl"
        onClick={() => setShowAddModal(true)}
      >
        <Plus className="h-6 w-6" />
      </Button>

      {/* Add Integration Modal */}
      {showAddModal && (
        <AddIntegrationModal
          onClose={() => setShowAddModal(false)}
          onIntegrationAdded={fetchData}
        />
      )}
    </div>
  )
}