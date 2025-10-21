import { useState, useEffect } from 'react'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Loader2, AlertCircle, Search, RefreshCw, ChevronLeft, ChevronRight } from 'lucide-react'
import { getAuthToken } from '@/utils/auth'
import { DeviceCard } from './DeviceCard'
import type { FieldComponentProps } from '../../../types'

interface MqttDevice {
  mqtt_path: string
  instance_id: string
  device_id: string
  state: Record<string, any>
  timestamp?: string
}

interface MqttDevicePickerValue {
  mqtt_path: string
  device_id: string
  instance_id: string
  extracted_data?: Record<string, any>
}

export function MqttDevicePickerField({
  field,
  value,
  onChange,
  error
}: FieldComponentProps<MqttDevicePickerValue>) {
  const [devices, setDevices] = useState<MqttDevice[]>([])
  const [filteredDevices, setFilteredDevices] = useState<MqttDevice[]>([])
  const [loading, setLoading] = useState(true)
  const [discoveryError, setDiscoveryError] = useState<string | null>(null)
  const [selectedDevice, setSelectedDevice] = useState<MqttDevice | null>(null)

  // Search and pagination state
  const [searchQuery, setSearchQuery] = useState('')
  const [currentPage, setCurrentPage] = useState(1)

  const config = field.config || {}

  // Configuration with defaults
  const connectorType = config.connector_type as string
  const itemsPerPage = (config.items_per_page as number) || 6
  const gridColumns = (config.grid_columns as number) || 3
  const enableSearch = config.enable_search !== false
  const searchableFields = (config.searchable_fields as string[]) || [
    'name',
    'device_id',
    'ip',
    'brand',
    'model'
  ]

  // Extract nested field from object
  const extractField = (obj: any, path: string): any => {
    return path.split('.').reduce((current, key) => current?.[key], obj)
  }

  // Debounced search
  useEffect(() => {
    const timer = setTimeout(() => {
      filterDevices(searchQuery)
    }, 300)

    return () => clearTimeout(timer)
  }, [searchQuery, devices])

  // Reset to first page when search changes
  useEffect(() => {
    setCurrentPage(1)
  }, [searchQuery])

  // Filter devices based on search query
  const filterDevices = (query: string) => {
    if (!query.trim()) {
      setFilteredDevices(devices)
      return
    }

    const queryLower = query.toLowerCase()

    const filtered = devices.filter((device) => {
      const state = device.state || {}

      return searchableFields.some((fieldPath) => {
        const value = extractField(state, fieldPath)
        return value?.toString().toLowerCase().includes(queryLower)
      })
    })

    setFilteredDevices(filtered)
  }

  // Pagination
  const totalPages = Math.ceil(filteredDevices.length / itemsPerPage)
  const startIndex = (currentPage - 1) * itemsPerPage
  const paginatedDevices = filteredDevices.slice(startIndex, startIndex + itemsPerPage)

  const goToNextPage = () => {
    if (currentPage < totalPages) {
      setCurrentPage((prev) => prev + 1)
    }
  }

  const goToPrevPage = () => {
    if (currentPage > 1) {
      setCurrentPage((prev) => prev - 1)
    }
  }

  // Keyboard navigation
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'ArrowLeft') {
        goToPrevPage()
      } else if (e.key === 'ArrowRight') {
        goToNextPage()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [currentPage, totalPages])

  // Discover devices on mount
  useEffect(() => {
    discoverDevices()
  }, [])

  const discoverDevices = async () => {
    if (!connectorType) {
      setDiscoveryError('connector_type is required in field config')
      setLoading(false)
      return
    }

    setLoading(true)
    setDiscoveryError(null)

    try {
      const token = getAuthToken()

      const requestBody = {
        connector_type: connectorType,
        mqtt_topic_pattern: config.mqtt_topic_pattern || null,
        instance_filter: config.instance_filter || null,
        base_topic_override: config.base_topic_override || null,
        search_query: null // Backend search not used, we filter client-side
      }

      const res = await fetch('/api/mqtt/discover-connector-devices', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify(requestBody)
      })

      if (!res.ok) {
        const errorText = await res.text()
        throw new Error(`Discovery failed: ${res.status} - ${errorText}`)
      }

      const discoveredDevices = await res.json()
      setDevices(discoveredDevices)
      setFilteredDevices(discoveredDevices)

      // Restore selected device if value exists
      if (value) {
        const selected = discoveredDevices.find(
          (d: MqttDevice) => d.mqtt_path === value.mqtt_path
        )
        if (selected) {
          setSelectedDevice(selected)
        }
      }
    } catch (err: any) {
      setDiscoveryError(err.message || 'Failed to discover devices')
    } finally {
      setLoading(false)
    }
  }

  const handleSelectDevice = (device: MqttDevice) => {
    setSelectedDevice(device)

    // Extract fields if configured
    const extractedData: Record<string, any> = {}

    if (config.extract_fields && Array.isArray(config.extract_fields)) {
      for (const fieldPath of config.extract_fields) {
        const value = extractField(device.state, fieldPath)
        // Use last part of path as key (e.g., 'stream_urls.mp4' -> 'mp4')
        const key = fieldPath.split('.').pop() || fieldPath
        extractedData[key] = value
      }
    }

    // Build output value based on save_mode
    const saveMode = config.save_mode || 'mqtt_path'

    let outputValue: MqttDevicePickerValue

    if (saveMode === 'extracted_fields') {
      outputValue = {
        mqtt_path: device.mqtt_path,
        device_id: device.device_id,
        instance_id: device.instance_id,
        extracted_data: extractedData
      }
    } else if (saveMode === 'full_state') {
      outputValue = {
        mqtt_path: device.mqtt_path,
        device_id: device.device_id,
        instance_id: device.instance_id,
        extracted_data: device.state
      }
    } else {
      // Default: just mqtt_path
      outputValue = {
        mqtt_path: device.mqtt_path,
        device_id: device.device_id,
        instance_id: device.instance_id
      }
    }

    onChange(outputValue)
  }

  // Grid columns class
  const gridColsClass = {
    1: 'grid-cols-1',
    2: 'grid-cols-2',
    3: 'grid-cols-3',
    4: 'grid-cols-4',
    5: 'grid-cols-5',
    6: 'grid-cols-6'
  }[gridColumns] || 'grid-cols-4'

  return (
    <div className="space-y-4">
      {/* Label */}
      <div>
        <Label>
          {field.label ?? 'Select Device'}
          {field.required && <span className="text-destructive ml-1">*</span>}
        </Label>
        {field.description && (
          <p className="text-xs text-muted-foreground mt-1">{field.description}</p>
        )}
      </div>

      {/* Search Bar */}
      {enableSearch && !loading && (
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder={`Search by ${searchableFields.slice(0, 3).join(', ')}...`}
              className="pl-10"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <Button variant="outline" size="icon" onClick={discoverDevices} title="Refresh">
            <RefreshCw className="h-4 w-4" />
          </Button>
        </div>
      )}

      {/* Error Alert */}
      {discoveryError && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{discoveryError}</AlertDescription>
        </Alert>
      )}

      {/* Field Error */}
      {error && (
        <Alert variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Loading State */}
      {loading && (
        <div className="flex flex-col items-center justify-center py-12 text-muted-foreground">
          <Loader2 className="h-8 w-8 animate-spin mb-3" />
          <p>Discovering {connectorType} devices...</p>
        </div>
      )}

      {/* Empty State */}
      {!loading && filteredDevices.length === 0 && !discoveryError && (
        <div className="flex flex-col items-center justify-center py-12 text-muted-foreground border-2 border-dashed rounded-lg">
          <AlertCircle className="h-8 w-8 mb-3" />
          {searchQuery ? (
            <p>No devices found matching &quot;{searchQuery}&quot;</p>
          ) : (
            <p>No {connectorType} devices found</p>
          )}
          <Button variant="link" onClick={() => setSearchQuery('')} className="mt-2">
            Clear search
          </Button>
        </div>
      )}

      {/* Devices Grid */}
      {!loading && filteredDevices.length > 0 && (
        <>
          {/* Results Info */}
          <div className="text-sm text-muted-foreground">
            Showing {startIndex + 1}-{Math.min(startIndex + itemsPerPage, filteredDevices.length)}{' '}
            of {filteredDevices.length} device{filteredDevices.length !== 1 ? 's' : ''}
          </div>

          {/* Grid - Fixed height cards, 2 rows of 3 = 6 cards visible */}
          <div className={`grid ${gridColsClass} gap-4 auto-rows-fr`}>
            {paginatedDevices.map((device, idx) => (
              <DeviceCard
                key={device.mqtt_path}
                device={device}
                isSelected={selectedDevice?.mqtt_path === device.mqtt_path}
                onSelect={() => handleSelectDevice(device)}
                config={{
                  show_preview: config.show_preview as boolean,
                  preview_field: config.preview_field as string,
                  card_title_field: config.card_title_field as string,
                  card_subtitle_field: config.card_subtitle_field as string,
                  icon_field: config.icon_field as string,
                  online_field: config.online_field as string,
                  connector_type: connectorType
                }}
                index={idx}
              />
            ))}
          </div>

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between pt-4 border-t">
              <div className="text-sm text-muted-foreground">
                Page {currentPage} of {totalPages}
              </div>

              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={goToPrevPage}
                  disabled={currentPage === 1}
                >
                  <ChevronLeft className="h-4 w-4 mr-1" />
                  Previous
                </Button>

                <Button
                  variant="outline"
                  size="sm"
                  onClick={goToNextPage}
                  disabled={currentPage === totalPages}
                >
                  Next
                  <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
              </div>
            </div>
          )}

          {/* Keyboard hint */}
          {totalPages > 1 && (
            <div className="text-xs text-center text-muted-foreground">
              Tip: Use ← → arrow keys to navigate pages
            </div>
          )}
        </>
      )}

      {/* Selection reminder */}
      {!loading && filteredDevices.length > 0 && !selectedDevice && (
        <Alert>
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>Please select a device by clicking &quot;Use&quot; to continue.</AlertDescription>
        </Alert>
      )}
    </div>
  )
}
