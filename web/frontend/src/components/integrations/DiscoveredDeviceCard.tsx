import { useTranslation } from 'react-i18next'
import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Plus, EyeOff } from 'lucide-react'
import BrandIcon from './BrandIcon'

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

interface DiscoveredDeviceCardProps {
  device: DiscoveredDevice
  onAdd: (device: DiscoveredDevice) => void
  onIgnore: (deviceId: string) => void
}

export default function DiscoveredDeviceCard({ device, onAdd, onIgnore }: DiscoveredDeviceCardProps) {
  const { t } = useTranslation()

  const formatTimestamp = (timestamp: string) => {
    const date = new Date(timestamp)
    const now = new Date()
    const diff = now.getTime() - date.getTime()
    const minutes = Math.floor(diff / 60000)
    
    if (minutes < 1) return t('Just now')
    if (minutes < 60) return t(`{{count}} minutes ago`, { count: minutes })
    const hours = Math.floor(minutes / 60)
    if (hours < 24) return t(`{{count}} hours ago`, { count: hours })
    const days = Math.floor(hours / 24)
    return t(`{{count}} days ago`, { count: days })
  }

  return (
    <Card className="hover:shadow-md transition-all">
      <CardContent className="p-4">
        <div className="flex items-start justify-between">
          <div className="flex items-start gap-3 flex-1">
            <BrandIcon 
              integration={device.integration}
              className="w-8 h-8 rounded"
              size={32}
            />
            
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <h4 className="font-semibold truncate">{device.name}</h4>
                <Badge variant="outline" className="text-xs">
                  {device.integration}
                </Badge>
              </div>
              
              <p className="text-sm text-muted-foreground">
                {device.manufacturer || device.integration}
              </p>

              <div className="mt-2 space-y-1 text-xs text-muted-foreground">
                {device.ip && (
                  <div className="flex justify-between">
                    <span>IP:</span>
                    <span className="font-mono">{device.ip}</span>
                  </div>
                )}
                {device.model && (
                  <div className="flex justify-between">
                    <span>Model:</span>
                    <span>{device.model}</span>
                  </div>
                )}
                <div className="flex justify-between">
                  <span>Found:</span>
                  <span>{formatTimestamp(device.discovered_at)}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div className="flex gap-2 mt-4">
          <Button 
            size="sm" 
            className="flex-1"
            onClick={() => onAdd(device)}
          >
            <Plus className="w-4 h-4 mr-1" />
            {t('Add')}
          </Button>
          
          <Button 
            size="sm" 
            variant="outline"
            onClick={() => onIgnore(device.id)}
          >
            <EyeOff className="w-4 h-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}