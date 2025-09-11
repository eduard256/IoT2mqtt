import { useTranslation } from 'react-i18next'
import { Card, CardContent } from '@/components/ui/card'
// @ts-ignore - Badge imported but not used warning
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { ChevronRight, Settings, AlertCircle, CheckCircle, Clock } from 'lucide-react'
import BrandIcon from './BrandIcon'

interface IntegrationCardProps {
  integration: {
    name: string
    display_name: string
    instances_count: number
    status: 'connected' | 'error' | 'offline' | 'configuring'
    last_seen?: string
  }
  onClick: () => void
}

export default function IntegrationCard({ integration, onClick }: IntegrationCardProps) {
  const { t } = useTranslation()

  const getStatusIcon = () => {
    switch (integration.status) {
      case 'connected':
        return <CheckCircle className="w-4 h-4 text-green-500" />
      case 'error':
        return <AlertCircle className="w-4 h-4 text-red-500" />
      case 'offline':
        return <Clock className="w-4 h-4 text-gray-500" />
      case 'configuring':
        return <Settings className="w-4 h-4 text-yellow-500" />
      default:
        return <Clock className="w-4 h-4 text-gray-500" />
    }
  }

  const getStatusText = () => {
    switch (integration.status) {
      case 'connected':
        return t('Connected')
      case 'error':
        return t('Error')
      case 'offline':
        return t('Offline')
      case 'configuring':
        return t('Configuring')
      default:
        return t('Unknown')
    }
  }

  const getStatusColor = () => {
    switch (integration.status) {
      case 'connected':
        return 'text-green-600'
      case 'error':
        return 'text-red-600'
      case 'offline':
        return 'text-gray-500'
      case 'configuring':
        return 'text-yellow-600'
      default:
        return 'text-gray-500'
    }
  }

  return (
    <Card 
      className="hover:shadow-lg transition-all cursor-pointer group border-l-4 border-l-blue-500"
      onClick={onClick}
    >
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <BrandIcon 
              integration={integration.name}
              className="w-10 h-10 rounded-lg"
              size={40}
            />
            
            <div className="flex-1">
              <div className="flex items-center gap-2">
                <h3 className="font-semibold text-lg">{integration.display_name}</h3>
                {getStatusIcon()}
              </div>
              
              <div className="flex items-center gap-3 mt-1">
                <span className="text-sm text-muted-foreground">
                  {integration.instances_count === 1 
                    ? t('{{count}} device', { count: integration.instances_count })
                    : t('{{count}} devices', { count: integration.instances_count })
                  }
                </span>
                
                <span className={`text-sm font-medium ${getStatusColor()}`}>
                  {getStatusText()}
                </span>
              </div>

              {integration.last_seen && (
                <span className="text-xs text-muted-foreground">
                  {t('Last seen')}: {new Date(integration.last_seen).toLocaleString()}
                </span>
              )}
            </div>
          </div>

          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              className="group-hover:bg-gray-100"
              onClick={(e) => {
                e.stopPropagation()
                onClick()
              }}
            >
              <Settings className="w-4 h-4" />
            </Button>
            
            <ChevronRight className="w-5 h-5 text-muted-foreground group-hover:text-foreground transition-colors" />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}