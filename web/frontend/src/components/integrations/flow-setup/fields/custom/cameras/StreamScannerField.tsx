import { useState, useEffect, useRef } from 'react'
import { Label } from '@/components/ui/label'
import { Button } from '@/components/ui/button'
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table'
import { Loader2, AlertCircle } from 'lucide-react'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { getAuthToken } from '@/utils/auth'
import type { FieldComponentProps } from '../../../types'

interface Stream {
  type: string
  protocol: string
  url: string
  full_url: string
  port: number
  notes?: string
}

export function StreamScannerField({ field, value, onChange, error }: FieldComponentProps<Stream>) {
  const [streams, setStreams] = useState<Stream[]>([])
  const [scanning, setScanning] = useState(true)
  const [scanError, setScanError] = useState<string | null>(null)
  const [selectedStream, setSelectedStream] = useState<Stream | null>(value || null)
  const eventSourceRef = useRef<EventSource | null>(null)

  const config = field.config || {}

  useEffect(() => {
    startScan()

    return () => {
      // Cleanup EventSource on unmount
      if (eventSourceRef.current) {
        eventSourceRef.current.close()
      }
    }
  }, [])

  const startScan = async () => {
    setScanning(true)
    setScanError(null)
    setStreams([])

    try {
      // Parse model data from JSON format (CameraModelPicker always returns JSON)
      const modelData = JSON.parse(config.model || '{}')

      const requestBody = {
        brand: modelData.brand,
        model: modelData.model,
        address: config.address || '',
        username: config.username || '',
        password: config.password || '',
        channel: parseInt(config.channel || '0')
      }

      const token = getAuthToken()

      // Start scan
      const scanRes = await fetch('/api/cameras/scan-streams', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify(requestBody)
      })

      if (!scanRes.ok) {
        const errorText = await scanRes.text()
        throw new Error(`Failed to start scan: ${scanRes.status} - ${errorText}`)
      }

      const scanData = await scanRes.json()

      if (!scanData.ok) {
        throw new Error(scanData.error || 'Scan failed')
      }

      const taskId = scanData.task_id

      // Open SSE connection
      const eventSource = new EventSource(
        `/api/cameras/scan-streams/${taskId}/stream?token=${token}`
      )
      eventSourceRef.current = eventSource

      eventSource.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data)

          if (data.type === 'done') {
            setScanning(false)
            eventSource.close()
          } else if (data.type === 'error') {
            setScanError(data.message || 'Scan error')
            setScanning(false)
            eventSource.close()
          } else {
            // New stream found
            const stream = data as Stream
            setStreams(prev => {
              const updated = [...prev, stream]
              // Sort by priority
              return updated.sort((a, b) => getPriority(a.type) - getPriority(b.type))
            })
          }
        } catch (err) {
          // Failed to parse SSE message
        }
      }

      eventSource.onerror = (err) => {
        setScanError('Connection error during scan')
        setScanning(false)
        eventSource.close()
      }

    } catch (err: any) {
      setScanError(err.message || 'Failed to start scan')
      setScanning(false)
    }
  }

  const getPriority = (type: string): number => {
    const priorities: Record<string, number> = {
      'ONVIF': 1,
      'FFMPEG': 2,
      'MJPEG': 3,
      'JPEG': 4,
      'VLC': 5
    }
    return priorities[type] || 99
  }

  const handleUse = (stream: Stream) => {
    setSelectedStream(stream)
    onChange(stream)
  }

  return (
    <div className="space-y-4">
      <div>
        <Label>
          {field.label ?? 'Available Streams'}
          {field.required && <span className="text-destructive ml-1">*</span>}
        </Label>
        {field.description && (
          <p className="text-xs text-muted-foreground mt-1">{field.description}</p>
        )}
      </div>

      {scanError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{scanError}</AlertDescription>
        </Alert>
      )}

      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="border rounded-md">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-[120px]">Type</TableHead>
              <TableHead>URL</TableHead>
              <TableHead className="w-[100px] text-right">Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {streams.length === 0 && scanning && !scanError && (
              <TableRow>
                <TableCell colSpan={3} className="text-center py-8">
                  <div className="flex flex-col items-center gap-2 text-muted-foreground">
                    <Loader2 className="h-6 w-6 animate-spin" />
                    <span>Scanning for camera streams...</span>
                  </div>
                </TableCell>
              </TableRow>
            )}

            {streams.length === 0 && !scanning && !scanError && (
              <TableRow>
                <TableCell colSpan={3} className="text-center py-8 text-muted-foreground">
                  No streams found. Please check your camera settings and try again.
                </TableCell>
              </TableRow>
            )}

            {streams.map((stream, idx) => {
              const isSelected = selectedStream?.url === stream.url

              return (
                <TableRow
                  key={idx}
                  className={isSelected ? 'bg-primary/5 border-l-4 border-l-primary' : ''}
                >
                  <TableCell className="font-medium">
                    <div className="flex items-center gap-2">
                      {stream.type}
                      {stream.type === 'ONVIF' && (
                        <span className="text-xs text-muted-foreground">(Recommended)</span>
                      )}
                    </div>
                  </TableCell>
                  <TableCell>
                    <div className="font-mono text-xs truncate max-w-md" title={stream.url}>
                      {stream.url}
                    </div>
                    {stream.notes && (
                      <div className="text-xs text-muted-foreground mt-1">{stream.notes}</div>
                    )}
                  </TableCell>
                  <TableCell className="text-right">
                    <Button
                      size="sm"
                      variant={isSelected ? "default" : "outline"}
                      onClick={() => handleUse(stream)}
                      disabled={isSelected}
                    >
                      {isSelected ? 'Selected' : 'Use'}
                    </Button>
                  </TableCell>
                </TableRow>
              )
            })}
          </TableBody>
        </Table>
      </div>

      {scanning && streams.length > 0 && (
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span>Still scanning for more streams...</span>
        </div>
      )}

      {!scanning && streams.length > 0 && !selectedStream && (
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            Please select a stream by clicking "Use" to continue.
          </AlertDescription>
        </Alert>
      )}
    </div>
  )
}
