import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { getAuthToken } from '@/utils/auth'
import { 
  Lightbulb, Thermometer, Lock, Speaker, Camera, Tv, 
  Power, Wifi, WifiOff, Settings, MoreVertical, 
  Sun, Moon, Loader2, AlertCircle, Home
} from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Slider } from '@/components/ui/slider'
import { Switch } from '@/components/ui/switch'
import { 
  DropdownMenu, 
  DropdownMenuContent, 
  DropdownMenuItem, 
  DropdownMenuLabel, 
  DropdownMenuSeparator, 
  DropdownMenuTrigger 
} from '@/components/ui/dropdown-menu'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { toast } from '@/hooks/use-toast'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

interface Device {
  device_id: string
  instance_id: string
  friendly_name: string
  device_type: string
  device_class?: string
  state: any
  online: boolean
  last_update?: string
  capabilities?: {
    brightness?: boolean
    color_temp?: boolean
    rgb?: boolean
    effects?: string[]
  }
  room?: string
  model?: string
  manufacturer?: string
}

interface Room {
  name: string
  icon: any
  devices: Device[]
}

export default function Devices() {
  const { t } = useTranslation()
  const [devices, setDevices] = useState<Device[]>([])
  const [loading, setLoading] = useState(true)
  const [selectedRoom, setSelectedRoom] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState('')
  // const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid')

  useEffect(() => {
    fetchDevices()
    // Set up polling for device updates
    const interval = setInterval(fetchDevices, 5000)
    return () => clearInterval(interval)
  }, [])

  const fetchDevices = async () => {
    try {
      const token = getAuthToken()
      if (!token) {
        throw new Error('No authentication token')
      }

      const response = await fetch('/api/devices', {
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (response.status === 401 || response.status === 403) {
        // Token expired or invalid, redirect to login
        localStorage.removeItem('token')
        window.location.href = '/login'
        return
      }

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      const data = await response.json()
      setDevices(data)
    } catch (error) {
      if (error instanceof Error && error.message !== 'No authentication token') {
        toast({
          title: t('Error'),
          description: t('Failed to load devices'),
          variant: 'destructive'
        })
      }
    } finally {
      setLoading(false)
    }
  }

  const handleDeviceControl = async (deviceId: string, command: any) => {
    try {
      const token = getAuthToken()
      if (!token) {
        throw new Error('No authentication token')
      }

      // Find the device to get instance_id
      const device = devices.find(d => d.device_id === deviceId)
      if (!device) {
        throw new Error('Device not found')
      }

      // Update local state optimistically
      setDevices(prev => prev.map(d => {
        if (d.device_id === deviceId) {
          return {
            ...d,
            state: { ...d.state, ...command }
          }
        }
        return d
      }))

      const response = await fetch(`/api/devices/${device.instance_id}/${deviceId}/command`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ command })
      })

      if (response.status === 401 || response.status === 403) {
        localStorage.removeItem('token')
        window.location.href = '/login'
        return
      }

      if (!response.ok) {
        throw new Error(`Failed to send command: ${response.status}`)
      }

      toast({
        title: t('Success'),
        description: t('Command sent to device'),
      })
    } catch (error) {
      // Revert optimistic update on error
      await fetchDevices()
      
      toast({
        title: t('Error'),
        description: t('Failed to control device'),
        variant: 'destructive'
      })
    }
  }

  const getDeviceIcon = (deviceType: string, deviceClass?: string) => {
    switch (deviceClass || deviceType) {
      case 'light': return Lightbulb
      case 'climate': return Thermometer
      case 'lock': return Lock
      case 'speaker': return Speaker
      case 'camera': return Camera
      case 'tv': return Tv
      default: return Power
    }
  }

  const getRoomIcon = (roomName: string) => {
    const icons: Record<string, any> = {
      'Bedroom': Moon,
      'Living Room': Tv,
      'Kitchen': Home,
      'Bathroom': Thermometer,
      'Office': Settings
    }
    return icons[roomName] || Home
  }

  // Group devices by room
  const rooms: Room[] = []
  const roomMap: Record<string, Device[]> = {}
  
  devices.forEach(device => {
    const room = device.room || 'Other'
    if (!roomMap[room]) {
      roomMap[room] = []
    }
    roomMap[room].push(device)
  })
  
  Object.entries(roomMap).forEach(([name, devices]) => {
    rooms.push({
      name,
      icon: getRoomIcon(name),
      devices
    })
  })

  // Filter devices
  const filteredDevices = devices.filter(device => {
    const matchesRoom = selectedRoom === 'all' || device.room === selectedRoom
    const matchesSearch = device.friendly_name.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          device.device_id.toLowerCase().includes(searchQuery.toLowerCase())
    return matchesRoom && matchesSearch
  })

  const DeviceCard = ({ device }: { device: Device }) => {
    const Icon = getDeviceIcon(device.device_type, device.device_class)
    const isLight = device.device_class === 'light'
    
    return (
      <Card className={`group transition-all duration-300 hover:shadow-lg ${!device.online ? 'opacity-60' : ''}`}>
        <CardHeader className="pb-3">
          <div className="flex items-start justify-between">
            <div className="flex items-center gap-3">
              <div className={`p-2 rounded-lg ${device.state?.power ? 'bg-primary/10 text-primary' : 'bg-muted'}`}>
                <Icon className="h-5 w-5" />
              </div>
              <div>
                <CardTitle className="text-base">{device.friendly_name}</CardTitle>
                <CardDescription className="text-xs">
                  {device.room} • {device.model}
                </CardDescription>
              </div>
            </div>
            
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" size="icon" className="h-8 w-8">
                  <MoreVertical className="h-4 w-4" />
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent align="end">
                <DropdownMenuLabel>{t('Device Options')}</DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem>
                  <Settings className="mr-2 h-4 w-4" />
                  {t('Settings')}
                </DropdownMenuItem>
                <DropdownMenuItem>
                  {t('View History')}
                </DropdownMenuItem>
                <DropdownMenuItem className="text-red-600">
                  {t('Remove')}
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
          
          <div className="flex items-center gap-2 mt-2">
            {device.online ? (
              <Badge variant="outline" className="text-xs">
                <Wifi className="mr-1 h-3 w-3" />
                {t('Online')}
              </Badge>
            ) : (
              <Badge variant="destructive" className="text-xs">
                <WifiOff className="mr-1 h-3 w-3" />
                {t('Offline')}
              </Badge>
            )}
            {device.manufacturer && (
              <Badge variant="secondary" className="text-xs">
                {device.manufacturer}
              </Badge>
            )}
          </div>
        </CardHeader>
        
        <CardContent className="space-y-4">
          {/* Power Switch */}
          <div className="flex items-center justify-between">
            <Label htmlFor={`power-${device.device_id}`}>{t('Power')}</Label>
            <Switch
              id={`power-${device.device_id}`}
              checked={device.state?.power || false}
              onCheckedChange={(checked) => handleDeviceControl(device.device_id, { power: checked })}
              disabled={!device.online}
            />
          </div>
          
          {/* Brightness Slider for Lights */}
          {isLight && device.capabilities?.brightness && device.state?.power && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>{t('Brightness')}</Label>
                <span className="text-sm text-muted-foreground">{device.state?.brightness || 0}%</span>
              </div>
              <Slider
                value={[device.state?.brightness || 0]}
                onValueChange={([value]) => handleDeviceControl(device.device_id, { brightness: value })}
                max={100}
                step={1}
                disabled={!device.online}
                className="w-full"
              />
            </div>
          )}
          
          {/* Color Temperature for Lights */}
          {isLight && device.capabilities?.color_temp && device.state?.power && (
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <Label>{t('Color Temperature')}</Label>
                <span className="text-sm text-muted-foreground">{device.state?.color_temp || 3000}K</span>
              </div>
              <Slider
                value={[device.state?.color_temp || 3000]}
                onValueChange={([value]) => handleDeviceControl(device.device_id, { color_temp: value })}
                min={2700}
                max={6500}
                step={100}
                disabled={!device.online}
                className="w-full"
              />
            </div>
          )}
          
          {/* RGB Color Picker for RGB Lights */}
          {isLight && device.capabilities?.rgb && device.state?.power && (
            <div className="space-y-2">
              <Label>{t('Color')}</Label>
              <div className="flex gap-2">
                <input
                  type="color"
                  value={device.state?.rgb || '#FFFFFF'}
                  onChange={(e) => handleDeviceControl(device.device_id, { rgb: e.target.value })}
                  disabled={!device.online}
                  className="h-10 w-full rounded-md border cursor-pointer"
                />
              </div>
            </div>
          )}
          
          {/* Effects for Lights */}
          {isLight && device.capabilities?.effects && device.state?.power && (
            <div className="space-y-2">
              <Label>{t('Effects')}</Label>
              <div className="grid grid-cols-2 gap-2">
                {device.capabilities.effects.map((effect) => (
                  <Button
                    key={effect}
                    variant="outline"
                    size="sm"
                    onClick={() => handleDeviceControl(device.device_id, { effect })}
                    disabled={!device.online}
                  >
                    {effect}
                  </Button>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-96">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="text-3xl font-bold">{t('devices.title')}</h1>
          <p className="text-muted-foreground mt-1">
            {t('Control and monitor your IoT devices')}
          </p>
        </div>
        
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon">
            <Settings className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Room Tabs */}
      <Tabs value={selectedRoom} onValueChange={setSelectedRoom}>
        <TabsList className="w-full justify-start overflow-x-auto">
          <TabsTrigger value="all">
            {t('All Devices')} ({devices.length})
          </TabsTrigger>
          {rooms.map((room) => {
            const RoomIcon = room.icon
            return (
              <TabsTrigger key={room.name} value={room.name} className="gap-2">
                <RoomIcon className="h-4 w-4" />
                {room.name} ({room.devices.length})
              </TabsTrigger>
            )
          })}
        </TabsList>

        {/* Search Bar */}
        <div className="mt-4">
          <Input
            type="text"
            placeholder={t('Search devices...')}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="max-w-sm"
          />
        </div>

        {/* Device Grid */}
        <TabsContent value={selectedRoom} className="mt-6">
          {filteredDevices.length === 0 ? (
            <Card className="p-12 text-center">
              <AlertCircle className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
              <p className="text-lg font-semibold mb-2">{t('No devices found')}</p>
              <p className="text-muted-foreground">
                {searchQuery 
                  ? t('No devices match your search')
                  : t('Add your first device from the Integrations page')
                }
              </p>
            </Card>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {filteredDevices.map((device) => (
                <DeviceCard key={device.device_id} device={device} />
              ))}
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* Stats Bar */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-primary/10 rounded-lg">
              <Power className="h-5 w-5 text-primary" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">{t('Total Devices')}</p>
              <p className="text-2xl font-bold">{devices.length}</p>
            </div>
          </div>
        </Card>
        
        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-green-500/10 rounded-lg">
              <Wifi className="h-5 w-5 text-green-500" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">{t('Online')}</p>
              <p className="text-2xl font-bold">
                {devices.filter(d => d.online).length}
              </p>
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-yellow-500/10 rounded-lg">
              <Sun className="h-5 w-5 text-yellow-500" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">{t('Active')}</p>
              <p className="text-2xl font-bold">
                {devices.filter(d => d.state?.power).length}
              </p>
            </div>
          </div>
        </Card>

        <Card className="p-4">
          <div className="flex items-center gap-3">
            <div className="p-2 bg-blue-500/10 rounded-lg">
              <Home className="h-5 w-5 text-blue-500" />
            </div>
            <div>
              <p className="text-sm text-muted-foreground">{t('Rooms')}</p>
              <p className="text-2xl font-bold">{rooms.length}</p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  )
}