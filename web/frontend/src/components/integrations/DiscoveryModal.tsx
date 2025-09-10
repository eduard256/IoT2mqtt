import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Search, Wifi, WifiOff, Loader2, AlertCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '@/components/ui/dialog'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { Alert, AlertDescription } from '@/components/ui/alert'

interface DiscoveryModalProps {
  onClose: () => void
  onIntegrationFound: (integration: any) => void
}

interface DiscoveredDevice {
  id: string
  name: string
  type: string
  ip?: string
  model?: string
  manufacturer?: string
  integration?: string
}

export default function DiscoveryModal({ onClose, onIntegrationFound }: DiscoveryModalProps) {
  const { t } = useTranslation()
  const [scanning, setScanning] = useState(false)
  const [progress, setProgress] = useState(0)
  const [devices, setDevices] = useState<DiscoveredDevice[]>([])
  const [error, setError] = useState<string | null>(null)

  const startDiscovery = async () => {
    setScanning(true)
    setError(null)
    setDevices([])
    setProgress(0)

    // Simulate discovery process
    // In real implementation, this would call multiple integration discovery endpoints
    try {
      // Mock discovery - replace with actual API calls
      const mockDevices: DiscoveredDevice[] = [
        {
          id: 'yeelight_1',
          name: 'Bedroom Light',
          type: 'Light',
          ip: '192.168.1.100',
          model: 'YLDD05YL',
          manufacturer: 'Yeelight',
          integration: 'yeelight'
        },
        {
          id: 'yeelight_2',
          name: 'Living Room Lamp',
          type: 'Light',
          ip: '192.168.1.101',
          model: 'YLXD76YL',
          manufacturer: 'Yeelight',
          integration: 'yeelight'
        }
      ]

      // Simulate progress
      for (let i = 0; i <= 100; i += 10) {
        setProgress(i)
        await new Promise(resolve => setTimeout(resolve, 200))
        
        // Add devices at certain progress points
        if (i === 30 && mockDevices.length > 0) {
          setDevices([mockDevices[0]])
        }
        if (i === 60 && mockDevices.length > 1) {
          setDevices([mockDevices[0], mockDevices[1]])
        }
      }

    } catch (err: any) {
      setError(err.message || 'Discovery failed')
    } finally {
      setScanning(false)
    }
  }

  const handleDeviceSelect = (device: DiscoveredDevice) => {
    if (device.integration) {
      // Mock integration data - in real app, fetch from API
      const integration = {
        name: device.integration,
        display_name: device.manufacturer || 'Unknown',
        branding: {
          icon: '💡',
          color: '#FFA500',
          background: 'linear-gradient(135deg, #FFA500 0%, #FF6B6B 100%)',
          category: 'lighting'
        }
      }
      
      onIntegrationFound(integration)
    }
  }

  return (
    <Dialog open={true} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Search className="h-5 w-5" />
            {t('Discover Devices on Your Network')}
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Instructions */}
          <Alert>
            <AlertCircle className="h-4 w-4" />
            <AlertDescription>
              {t('Discovery will scan your local network for compatible devices. Make sure your devices are powered on and connected to the same network.')}
            </AlertDescription>
          </Alert>

          {/* Progress */}
          {scanning && (
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm">
                <span className="text-muted-foreground">{t('Scanning network...')}</span>
                <span className="font-medium">{progress}%</span>
              </div>
              <Progress value={progress} className="h-2" />
            </div>
          )}

          {/* Discovered Devices */}
          {devices.length > 0 && (
            <div className="space-y-3">
              <h3 className="font-semibold text-sm text-muted-foreground uppercase tracking-wider">
                {t('Discovered Devices')} ({devices.length})
              </h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {devices.map((device) => (
                  <Card 
                    key={device.id}
                    className="p-4 cursor-pointer hover:shadow-lg transition-all hover:scale-105"
                    onClick={() => handleDeviceSelect(device)}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-3">
                        <div className="p-2 bg-primary/10 rounded-lg">
                          <Wifi className="h-5 w-5 text-primary" />
                        </div>
                        <div>
                          <h4 className="font-semibold">{device.name}</h4>
                          <p className="text-sm text-muted-foreground">{device.type}</p>
                          {device.ip && (
                            <p className="text-xs text-muted-foreground mt-1">
                              IP: {device.ip}
                            </p>
                          )}
                        </div>
                      </div>
                      
                      <div className="text-right">
                        {device.manufacturer && (
                          <Badge variant="secondary">{device.manufacturer}</Badge>
                        )}
                        {device.model && (
                          <p className="text-xs text-muted-foreground mt-1">
                            {device.model}
                          </p>
                        )}
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            </div>
          )}

          {/* No Devices Found */}
          {!scanning && devices.length === 0 && progress > 0 && (
            <div className="text-center py-8">
              <WifiOff className="h-12 w-12 text-muted-foreground mx-auto mb-3" />
              <p className="text-muted-foreground">
                {t('No devices found. Make sure your devices are powered on and on the same network.')}
              </p>
            </div>
          )}

          {/* Error */}
          {error && (
            <Alert variant="destructive">
              <AlertCircle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={onClose}>
            {t('Cancel')}
          </Button>
          <Button 
            onClick={startDiscovery} 
            disabled={scanning}
          >
            {scanning ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                {t('Scanning...')}
              </>
            ) : (
              <>
                <Search className="mr-2 h-4 w-4" />
                {t('Start Discovery')}
              </>
            )}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}