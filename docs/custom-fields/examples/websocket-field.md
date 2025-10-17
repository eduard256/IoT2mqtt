# Example: WebSocket Field

This example shows how to create a field that maintains a WebSocket connection for real-time data.

## Live Device Discovery Field

A field that connects to a WebSocket endpoint to discover devices in real-time.

### 1. Create Component

```typescript
// web/frontend/src/components/integrations/flow-setup/fields/custom/yeelight/LiveDiscoveryField.tsx
import { useState, useEffect, useRef } from 'react'
import { Loader2, Wifi, WifiOff } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'
import type { FieldComponentProps } from '../../../types'

interface Device {
  id: string
  name: string
  ip: string
  model: string
  fw_ver: string
}

export function LiveDiscoveryField({ field, value, onChange }: FieldComponentProps<string[]>) {
  const [devices, setDevices] = useState<Device[]>([])
  const [connected, setConnected] = useState(false)
  const [discovering, setDiscovering] = useState(false)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    connectWebSocket()

    return () => {
      disconnectWebSocket()
    }
  }, [])

  const connectWebSocket = () => {
    try {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const ws = new WebSocket(`${protocol}//${window.location.host}/ws/discovery/yeelight`)
      wsRef.current = ws

      ws.onopen = () => {
        console.log('WebSocket connected')
        setConnected(true)
      }

      ws.onmessage = (event) => {
        const message = JSON.parse(event.data)

        if (message.type === 'device_discovered') {
          setDevices(prev => {
            const exists = prev.find(d => d.id === message.device.id)
            if (exists) return prev
            return [...prev, message.device]
          })
        } else if (message.type === 'discovery_started') {
          setDiscovering(true)
        } else if (message.type === 'discovery_stopped') {
          setDiscovering(false)
        }
      }

      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        setConnected(false)
      }

      ws.onclose = () => {
        console.log('WebSocket disconnected')
        setConnected(false)
      }
    } catch (error) {
      console.error('Failed to connect WebSocket:', error)
    }
  }

  const disconnectWebSocket = () => {
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
  }

  const startDiscovery = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'start_discovery' }))
    }
  }

  const stopDiscovery = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action: 'stop_discovery' }))
    }
  }

  const toggleDevice = (deviceId: string) => {
    const selected = value ?? []
    const newValue = selected.includes(deviceId)
      ? selected.filter(id => id !== deviceId)
      : [...selected, deviceId]
    onChange(newValue)
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <Label>
          {field.label ?? 'Discovered Devices'}
          {field.required && <span className="text-destructive ml-1">*</span>}
        </Label>
        <div className="flex items-center gap-2">
          <Badge variant={connected ? 'success' : 'destructive'} className="text-xs">
            {connected ? (
              <>
                <Wifi className="h-3 w-3 mr-1" />
                Connected
              </>
            ) : (
              <>
                <WifiOff className="h-3 w-3 mr-1" />
                Disconnected
              </>
            )}
          </Badge>
          {discovering ? (
            <Button size="sm" variant="outline" onClick={stopDiscovery}>
              <Loader2 className="h-3 w-3 mr-1 animate-spin" />
              Stop Discovery
            </Button>
          ) : (
            <Button size="sm" onClick={startDiscovery} disabled={!connected}>
              Start Discovery
            </Button>
          )}
        </div>
      </div>

      {field.description && (
        <p className="text-xs text-muted-foreground">{field.description}</p>
      )}

      <div className="space-y-2">
        {devices.length === 0 ? (
          <div className="text-center py-8 text-muted-foreground">
            {discovering ? (
              <div className="flex flex-col items-center gap-2">
                <Loader2 className="h-6 w-6 animate-spin" />
                <span>Searching for devices...</span>
              </div>
            ) : (
              <span>No devices discovered yet. Click "Start Discovery" to begin.</span>
            )}
          </div>
        ) : (
          devices.map(device => {
            const isSelected = (value ?? []).includes(device.id)

            return (
              <Card
                key={device.id}
                className={cn(
                  'cursor-pointer transition-all hover:shadow-md',
                  isSelected ? 'border-primary bg-primary/5' : 'border-border'
                )}
                onClick={() => toggleDevice(device.id)}
              >
                <CardContent className="p-3">
                  <div className="flex justify-between items-start">
                    <div className="flex-1">
                      <div className="font-medium">{device.name}</div>
                      <div className="text-sm text-muted-foreground">{device.ip}</div>
                      <div className="flex gap-2 mt-1">
                        <Badge variant="outline" className="text-xs">{device.model}</Badge>
                        <Badge variant="outline" className="text-xs">v{device.fw_ver}</Badge>
                      </div>
                    </div>
                    {isSelected && (
                      <Badge variant="default">Selected</Badge>
                    )}
                  </div>
                </CardContent>
              </Card>
            )
          })
        )}
      </div>
    </div>
  )
}
```

### 2. Backend WebSocket Handler

```python
# Example WebSocket endpoint (FastAPI)
from fastapi import WebSocket, WebSocketDisconnect
import asyncio
import json

@router.websocket('/ws/discovery/yeelight')
async def yeelight_discovery_websocket(websocket: WebSocket):
    await websocket.accept()
    discovering = False
    discovery_task = None

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            if message['action'] == 'start_discovery':
                if not discovering:
                    discovering = True
                    await websocket.send_json({'type': 'discovery_started'})
                    discovery_task = asyncio.create_task(
                        discover_devices(websocket)
                    )

            elif message['action'] == 'stop_discovery':
                if discovering and discovery_task:
                    discovery_task.cancel()
                    discovering = False
                    await websocket.send_json({'type': 'discovery_stopped'})

    except WebSocketDisconnect:
        if discovery_task:
            discovery_task.cancel()

async def discover_devices(websocket: WebSocket):
    """Continuously discover Yeelight devices"""
    try:
        while True:
            # Your discovery logic here (e.g., SSDP multicast)
            devices = await find_yeelight_devices()

            for device in devices:
                await websocket.send_json({
                    'type': 'device_discovered',
                    'device': {
                        'id': device['id'],
                        'name': device['name'],
                        'ip': device['ip'],
                        'model': device['model'],
                        'fw_ver': device['fw_ver']
                    }
                })

            await asyncio.sleep(2)  # Discovery interval

    except asyncio.CancelledError:
        pass
```

### 3. Register Field

```typescript
// web/frontend/src/components/integrations/flow-setup/fields/custom/yeelight/index.ts
import { fieldRegistry } from '../../registry'
import { LiveDiscoveryField } from './LiveDiscoveryField'

fieldRegistry.registerCustom({
  type: 'yeelight_live_discovery',
  component: LiveDiscoveryField,
  connectors: ['yeelight'],
  displayName: 'Yeelight Live Discovery',
  description: 'Discover Yeelight devices in real-time'
})
```

### 4. Use in setup.json

```json
{
  "flows": [{
    "id": "discovery_flow",
    "name": "Discover Devices",
    "steps": [{
      "id": "discover",
      "type": "form",
      "title": "Device Discovery",
      "description": "Automatically discover Yeelight devices on your network",
      "schema": {
        "fields": [
          {
            "type": "yeelight_live_discovery",
            "name": "discovered_devices",
            "label": "Yeelight Devices",
            "description": "Select the devices you want to add",
            "required": true
          }
        ]
      }
    }]
  }]
}
```

### Key Features

- **Real-time Updates**: Devices appear as they're discovered
- **Connection Status**: Shows WebSocket connection state
- **Start/Stop Control**: User can control discovery process
- **Cleanup**: Properly closes WebSocket on unmount
- **Multi-select**: Users can select multiple devices
- **Visual Feedback**: Shows discovery progress

### Advanced: Reconnection Logic

Add automatic reconnection:

```typescript
const reconnectIntervalRef = useRef<NodeJS.Timeout | null>(null)

const connectWebSocket = () => {
  // ... connection logic ...

  ws.onclose = () => {
    setConnected(false)
    // Attempt reconnection after 5 seconds
    reconnectIntervalRef.current = setTimeout(() => {
      connectWebSocket()
    }, 5000)
  }
}

useEffect(() => {
  return () => {
    if (reconnectIntervalRef.current) {
      clearTimeout(reconnectIntervalRef.current)
    }
  }
}, [])
```
