import { Card, CardContent } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Camera, Lightbulb, Server, AlertCircle } from 'lucide-react'
import { cn } from '@/lib/utils'

interface DeviceCardProps {
  device: {
    mqtt_path: string
    instance_id: string
    device_id: string
    state: Record<string, any>
    timestamp?: string
  }
  isSelected: boolean
  onSelect: () => void
  config: {
    show_preview?: boolean
    preview_field?: string
    card_title_field?: string
    card_subtitle_field?: string
    icon_field?: string
    online_field?: string
    connector_type?: string
  }
  index: number
}

export function DeviceCard({ device, isSelected, onSelect, config, index }: DeviceCardProps) {
  const state = device.state || {}

  // Extract fields from config
  const titleField = config.card_title_field || 'name'
  const subtitleField = config.card_subtitle_field || 'brand'
  const onlineField = config.online_field || 'online'
  const previewField = config.preview_field || 'stream_urls.jpeg'

  // Get field values
  const extractField = (obj: any, path: string): any => {
    return path.split('.').reduce((current, key) => current?.[key], obj)
  }

  const title = extractField(state, titleField) || device.device_id
  const subtitle = extractField(state, subtitleField) || ''
  const isOnline = extractField(state, onlineField) ?? true
  const previewUrl = config.show_preview ? extractField(state, previewField) : null

  // Get icon based on connector type
  const getIcon = () => {
    const connectorType = config.connector_type?.toLowerCase()

    switch (connectorType) {
      case 'cameras':
      case 'camera':
        return <Camera className="h-5 w-5" />
      case 'yeelight':
      case 'light':
      case 'lighting':
        return <Lightbulb className="h-5 w-5" />
      default:
        return <Server className="h-5 w-5" />
    }
  }

  // Get additional metadata to display
  const getMetadata = () => {
    const metadata: Array<{ label: string; value: string }> = []

    if (state.ip) {
      metadata.push({ label: 'IP', value: state.ip })
    }

    if (state.model) {
      metadata.push({ label: 'Model', value: state.model })
    }

    // Show truncated instance ID
    const shortInstanceId = device.instance_id.slice(-8)
    metadata.push({ label: 'Instance', value: `...${shortInstanceId}` })

    return metadata
  }

  const metadata = getMetadata()

  return (
    <Card
      className={cn(
        'cursor-pointer transition-all duration-200 hover:shadow-lg hover:scale-[1.02]',
        'animate-in fade-in slide-in-from-bottom-2 h-full',
        'flex flex-col',
        isSelected && 'border-l-4 border-l-primary bg-primary/5 shadow-md'
      )}
      style={{
        animationDelay: `${index * 50}ms`,
        animationDuration: '300ms'
      }}
    >
      {/* Preview Image (for cameras) */}
      {previewUrl && (
        <div className="relative w-full h-32 bg-muted overflow-hidden rounded-t-md flex-shrink-0">
          <img
            src={previewUrl}
            alt={title}
            className="w-full h-full object-cover"
            onError={(e) => {
              // Fallback if image fails to load
              e.currentTarget.style.display = 'none'
            }}
          />
          {!isOnline && (
            <div className="absolute inset-0 bg-black/50 flex items-center justify-center">
              <AlertCircle className="h-6 w-6 text-white" />
            </div>
          )}
        </div>
      )}

      <CardContent className="p-3 flex flex-col flex-1">
        {/* Header */}
        <div className="flex items-start gap-2 mb-2">
          <div className="mt-0.5 flex-shrink-0">{getIcon()}</div>
          <div className="flex-1 min-w-0">
            <h3
              className="font-medium truncate text-sm leading-tight"
              title={title}
            >
              {title}
            </h3>
            {subtitle && (
              <p className="text-xs text-muted-foreground truncate leading-tight" title={subtitle}>
                {subtitle}
              </p>
            )}
          </div>
        </div>

        {/* Status Badge and Info - Compact */}
        <div className="flex items-center gap-2 mb-2 flex-wrap">
          {isOnline ? (
            <Badge variant="default" className="bg-green-500 hover:bg-green-600 text-xs px-2 py-0">
              <span className="inline-block w-1 h-1 rounded-full bg-white mr-1" />
              Online
            </Badge>
          ) : (
            <Badge variant="secondary" className="text-xs px-2 py-0">
              <span className="inline-block w-1 h-1 rounded-full bg-muted-foreground mr-1" />
              Offline
            </Badge>
          )}
          {state.ip && (
            <span className="text-xs text-muted-foreground font-mono">{state.ip}</span>
          )}
        </div>

        {/* Spacer to push button to bottom */}
        <div className="flex-1" />

        {/* Select Button */}
        <Button
          className="w-full mt-2"
          variant={isSelected ? 'default' : 'outline'}
          size="sm"
          onClick={onSelect}
          disabled={isSelected}
        >
          {isSelected ? '✓ Selected' : 'Use'}
        </Button>
      </CardContent>
    </Card>
  )
}
