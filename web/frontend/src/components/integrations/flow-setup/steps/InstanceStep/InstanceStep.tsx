import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Loader2 } from 'lucide-react'
import { DeviceListItem } from '../../components/DeviceListItem'
import { buildCurrentDevice, isDuplicateDevice, normalizeDeviceId } from '../../utils/deviceUtils'
import { getAuthToken } from '@/utils/auth'
import type { StepComponentProps } from '../../types'
import type { FlowSetupSchema } from '@/types/integration'

interface InstanceStepProps extends StepComponentProps {
  schema: FlowSetupSchema | null
  collectedDevices: any[]
  onAddDevice: () => void
  onEditDevice: (index: number) => void
  onRemoveDevice: (index: number) => void
  onSuccess: () => void
}

export function InstanceStep({
  step,
  flowState,
  context,
  busy,
  setBusy,
  setError,
  mode,
  existingInstanceId,
  initialConfig,
  connectorName,
  schema,
  collectedDevices,
  onAddDevice,
  onEditDevice,
  onRemoveDevice,
  onSuccess
}: InstanceStepProps) {
  const createInstance = async () => {
    if (!step.instance) {
      setError('Instance step missing configuration')
      return
    }

    setBusy(true)
    setError(null)

    try {
      let instanceId: string
      let friendlyName: string
      let config: any
      let connectorType: string
      let enabled: boolean
      let updateInterval: number
      let secrets: any

      // Edit mode: use existing instance data
      if (mode === 'edit') {
        instanceId = existingInstanceId!

        const formFriendlyName = flowState.form.device_config?.friendly_name
        friendlyName = formFriendlyName || initialConfig.friendly_name || instanceId

        const resolved = resolveDeepPayload(step.instance, context)
        config = resolved.config ?? initialConfig.config ?? {}
        connectorType = connectorName
        enabled = initialConfig.enabled ?? true
        updateInterval = initialConfig.update_interval ?? 15
        secrets = resolved.secrets ?? initialConfig.secrets ?? undefined
      } else {
        // Create mode
        const resolved = resolveDeepPayload(step.instance, context)

        // Send instance_id to backend (will be auto-generated if null/empty/"auto")
        instanceId = resolved.instance_id || null

        friendlyName = resolved.friendly_name ?? connectorName
        config = resolved.config ?? {}
        connectorType = resolved.connector_type ?? connectorName
        enabled = resolved.enabled ?? true
        updateInterval = resolved.update_interval ?? 15
        secrets = resolved.secrets ?? undefined
      }

      // Collect devices
      let devices = []
      if (schema?.multi_device?.enabled) {
        devices = [...collectedDevices]
        const currentDevice = buildCurrentDevice(flowState)
        if (currentDevice && !isDuplicateDevice(currentDevice, devices)) {
          devices.push(currentDevice)
        }
      } else {
        if (mode === 'edit') {
          devices = collectedDevices
        } else {
          const resolved = resolveDeepPayload(step.instance, context)
          devices = resolved.devices ?? []
        }
      }

      const payload = {
        instance_id: instanceId,  // Can be null - backend will auto-generate
        connector_type: connectorType,
        friendly_name: friendlyName,
        config: config,
        devices: devices,
        enabled: enabled,
        update_interval: updateInterval,
        secrets: secrets
      }

      // Normalize numeric fields
      if (typeof payload.update_interval === 'string') {
        const trimmed = payload.update_interval.trim()
        const numeric = Number(trimmed)
        payload.update_interval = trimmed && Number.isFinite(numeric) ? numeric : 15
      }

      if (payload.config && typeof payload.config.duration === 'string') {
        const trimmed = payload.config.duration.trim()
        const numericDuration = Number(trimmed)
        payload.config.duration = trimmed && Number.isFinite(numericDuration) ? numericDuration : 300
      }

      if (payload.config && typeof payload.config.discovery_interval === 'string') {
        const trimmed = payload.config.discovery_interval.trim()
        const numericInterval = Number(trimmed)
        if (trimmed && Number.isFinite(numericInterval)) {
          payload.config.discovery_interval = numericInterval
        }
      }

      // Normalize devices
      if (payload.devices && Array.isArray(payload.devices)) {
        payload.devices = payload.devices.map(device => {
          const mapped = { ...device }

          if (mapped.device_id && typeof mapped.device_id === 'string') {
            mapped.device_id = normalizeDeviceId(mapped.device_id)
          }

          if (typeof mapped.port === 'string') {
            const trimmed = mapped.port.trim()
            const numericPort = Number(trimmed)
            mapped.port = trimmed && Number.isFinite(numericPort) ? numericPort : 55443
          }

          return mapped
        })
      }

      const token = getAuthToken()
      const method = mode === 'edit' ? 'PUT' : 'POST'
      const url =
        mode === 'edit'
          ? `/api/instances/${connectorType}/${existingInstanceId}`
          : '/api/instances'

      const response = await fetch(url, {
        method,
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      })

      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(data?.detail ?? `Failed to ${mode === 'edit' ? 'update' : 'create'} instance`)
      }

      onSuccess()
    } catch (e: any) {
      setError(e?.message ?? 'Failed to create instance')
    } finally {
      setBusy(false)
    }
  }

  // Multi-device support
  const multiDevice = schema?.multi_device
  console.log('[InstanceStep] Multi-device config:', multiDevice)
  console.log('[InstanceStep] Collected devices:', collectedDevices)
  console.log('[InstanceStep] FlowState:', flowState)

  const currentDevice = buildCurrentDevice(flowState)
  console.log('[InstanceStep] Current device from buildCurrentDevice:', currentDevice)

  // All devices for display
  const allDevices = [...collectedDevices]
  console.log('[InstanceStep] allDevices (before current):', allDevices)

  const hasCurrentDevice = currentDevice && !isDuplicateDevice(currentDevice, allDevices)
  console.log('[InstanceStep] hasCurrentDevice:', hasCurrentDevice)
  console.log('[InstanceStep] currentDevice is duplicate?', currentDevice && isDuplicateDevice(currentDevice, allDevices))

  if (hasCurrentDevice) {
    allDevices.push(currentDevice)
    console.log('[InstanceStep] ✅ Added current device to allDevices')
  }

  const maxDevices = multiDevice?.max_devices ?? 100
  const canAddMore = multiDevice?.enabled === true && allDevices.length < maxDevices
  const totalDeviceCount = allDevices.length

  console.log('[InstanceStep] Final allDevices:', allDevices)
  console.log('[InstanceStep] Total device count:', totalDeviceCount)

  return (
    <Card>
      <CardHeader>
        <CardTitle>{step.title ?? 'Create Instance'}</CardTitle>
        {step.description && <CardDescription>{step.description}</CardDescription>}
      </CardHeader>
      <CardContent className="space-y-4">
        {/* Device list */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-semibold text-foreground">
              {multiDevice?.enabled
                ? `${multiDevice.device_label ?? 'Devices'} (${totalDeviceCount}/${maxDevices})`
                : 'Device Configuration'}
            </h4>
          </div>
          <div className="space-y-2">
            {allDevices.map((device, index) => {
              const isCurrentDevice = hasCurrentDevice && index === allDevices.length - 1

              return (
                <DeviceListItem
                  key={`${device.device_id}-${index}`}
                  device={device}
                  index={index}
                  onRemove={isCurrentDevice ? undefined : () => onRemoveDevice(index)}
                  onEdit={isCurrentDevice ? undefined : () => onEditDevice(index)}
                  canRemove={!isCurrentDevice && (multiDevice?.enabled === true || allDevices.length > 1)}
                />
              )
            })}
          </div>
        </div>

        {/* Add another device button */}
        {canAddMore && (
          <Button variant="outline" onClick={onAddDevice} disabled={busy} className="w-full">
            {multiDevice!.add_button_label ?? 'Add Another Device'}
          </Button>
        )}

        <p className="text-sm text-muted-foreground">
          Press {mode === 'edit' ? 'Save Changes' : 'Finish'} to {mode === 'edit' ? 'update' : 'create'} the
          connector instance with {totalDeviceCount} device{totalDeviceCount > 1 ? 's' : ''}.
        </p>

        <Button onClick={createInstance} disabled={busy} className="w-full">
          {busy && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
          {mode === 'edit' ? 'Save Changes' : 'Finish'}
        </Button>
      </CardContent>
    </Card>
  )
}

// Helper function
function resolveDeepPayload(payload: any, context: any): any {
  if (payload == null) return payload

  if (typeof payload === 'string') {
    return resolveTemplate(payload, context)
  }

  if (Array.isArray(payload)) {
    return payload.map(item => resolveDeepPayload(item, context))
  }

  if (typeof payload === 'object') {
    const result: Record<string, any> = {}
    for (const [key, val] of Object.entries(payload)) {
      result[key] = resolveDeepPayload(val, context)
    }
    return result
  }

  return payload
}

function resolveTemplate(value: any, context: any): any {
  if (typeof value !== 'string') return value

  const singleMatch = value.match(/^{{\s*([^}]+)\s*}}$/)
  if (singleMatch) {
    const path = singleMatch[1].trim()
    const segments = path.split('.').map(s => s.trim()).filter(s => s)
    let pointer: any = context
    for (const segment of segments) {
      if (pointer == null) return ''
      pointer = pointer[segment]
    }
    return pointer ?? ''
  }

  const matcher = /{{\s*([^}]+)\s*}}/g
  return value.replace(matcher, (_, rawPath) => {
    const path = rawPath.trim()
    const segments = path.split('.').map(s => s.trim()).filter(s => s)
    let pointer: any = context
    for (const segment of segments) {
      if (pointer == null) return ''
      pointer = pointer[segment]
    }
    if (pointer == null) return ''
    if (typeof pointer === 'object') return JSON.stringify(pointer)
    return String(pointer)
  })
}
