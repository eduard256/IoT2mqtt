import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { getAuthToken } from '@/utils/auth'
import { Search, Loader2, Check, AlertCircle, ChevronDown, ChevronUp } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { toast } from '@/hooks/use-toast'
import BrandIcon from './BrandIcon'

interface Integration {
  name: string
  display_name: string
  manual_config?: {
    fields: Array<{
      name: string
      type: string
      label: string
      required: boolean
      default?: any
      placeholder?: string
      validation?: any
      options?: Array<{ value: string; label: string }>
      min?: number
      max?: number
      step?: number
    }>
  }
}

interface DiscoveredDevice {
  id: string
  name: string
  ip: string
  model?: string
  capabilities?: Record<string, any>
  integration?: string
}

interface DeviceSetupFormProps {
  integration: Integration
  onCancel: () => void
  onSuccess: () => void
}

export default function DeviceSetupForm({ integration, onCancel, onSuccess }: DeviceSetupFormProps) {
  const { t } = useTranslation()
  const [formData, setFormData] = useState<Record<string, any>>({})
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [saving, setSaving] = useState(false)
  const [autoDiscovering, setAutoDiscovering] = useState(false)
  const [discoveredDevices, setDiscoveredDevices] = useState<DiscoveredDevice[]>([])
  const [showDiscovery, setShowDiscovery] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)

  // Initialize form with defaults
  useEffect(() => {
    const initialData: Record<string, any> = {}
    integration.manual_config?.fields.forEach(field => {
      if (field.default !== undefined) {
        initialData[field.name] = field.default
      }
    })
    setFormData(initialData)
  }, [integration])

  // Start auto discovery when IP field changes
  useEffect(() => {
    const ipField = integration.manual_config?.fields.find(f => f.type === 'ip')
    if (ipField && formData[ipField.name]) {
      const ip = formData[ipField.name]
      if (isValidIP(ip)) {
        startAutoDiscovery()
      }
    }
  }, [formData, integration])

  const isValidIP = (ip: string): boolean => {
    const ipRegex = /^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$/
    return ipRegex.test(ip) && ip.split('.').every(octet => parseInt(octet) <= 255)
  }

  const startAutoDiscovery = async () => {
    if (autoDiscovering) return
    
    setAutoDiscovering(true)
    setShowDiscovery(true)
    setDiscoveredDevices([])

    try {
      const token = getAuthToken()
      const response = await fetch(`/api/discovery/scan/${integration.name}`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        }
      })

      if (response.ok) {
        // Poll for discovery results
        const pollInterval = setInterval(async () => {
          try {
            const statusResponse = await fetch('/api/discovery/status', {
              headers: {
                'Authorization': `Bearer ${token}`,
                'Content-Type': 'application/json'
              }
            })
            
            if (statusResponse.ok) {
              const statusData = await statusResponse.json()
              if (statusData.devices && statusData.devices.length > 0) {
                // Filter devices for current integration
                const filteredDevices = statusData.devices.filter((d: DiscoveredDevice) => 
                  d.integration === integration.name
                )
                setDiscoveredDevices(filteredDevices)
                clearInterval(pollInterval)
                setAutoDiscovering(false)
              }
            }
          } catch (error) {
            console.error('Discovery poll error:', error)
          }
        }, 2000)
        
        // Stop polling after timeout
        setTimeout(() => {
          clearInterval(pollInterval)
          setAutoDiscovering(false)
        }, 30000) // 30 seconds timeout
      }
    } catch (error) {
      setAutoDiscovering(false)
      console.error('Discovery failed:', error)
    }
  }

  const handleDiscoveredDeviceSelect = (device: DiscoveredDevice) => {
    // Auto-fill form with discovered device data
    const newFormData = { ...formData }
    
    // Set IP
    const ipField = integration.manual_config?.fields.find(f => f.type === 'ip')
    if (ipField) {
      newFormData[ipField.name] = device.ip
    }

    // Set name
    const nameField = integration.manual_config?.fields.find(f => f.name === 'name')
    if (nameField) {
      newFormData[nameField.name] = device.name
    }

    // Set model if available
    if (device.model) {
      const modelField = integration.manual_config?.fields.find(f => f.name === 'model')
      if (modelField) {
        newFormData[modelField.name] = device.model
      }
    }

    setFormData(newFormData)
    setShowDiscovery(false)
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    // Validate required fields only (IP and Name)
    const newErrors: Record<string, string> = {}
    
    // IP is required
    if (!formData.ip) {
      newErrors.ip = t('{{field}} is required', { field: t('discovery.ip_address') })
    }
    
    // Name is required
    if (!formData.name) {
      newErrors.name = t('{{field}} is required', { field: t('discovery.device_name') })
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors)
      return
    }

    setSaving(true)
    setErrors({})

    try {
      const token = getAuthToken()
      
      // Generate instance_id if not provided
      const instanceId = `${integration.name}_${formData.ip.replace(/\./g, '_')}_${Date.now()}`
      
      const response = await fetch('/api/discovery/manual', {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          integration: integration.name,
          instance_id: instanceId,
          friendly_name: formData.name || 'My Device',
          ip: formData.ip,
          port: formData.port || integration.manual_config?.fields.find((f: any) => f.name === 'port')?.default || 55443,
          name: formData.name,
          model: formData.model || integration.manual_config?.fields.find((f: any) => f.name === 'model')?.default || 'color',
          config: {
            ...formData,
            transition: formData.transition || 300,
            effect: formData.effect || 'smooth'
          }
        })
      })

      if (response.ok) {
        toast({
          title: t('common.success'),
          description: t('Device added successfully')
        })
        onSuccess()
      } else {
        const errorData = await response.json().catch(() => ({ detail: 'Failed to add device' }))
        throw new Error(errorData.detail || 'Failed to add device')
      }
    } catch (error: any) {
      console.error('Failed to add device:', error)
      toast({
        title: t('common.error'),
        description: error.message || 'Failed to add device',
        variant: 'destructive'
      })
    } finally {
      setSaving(false)
    }
  }

  const renderField = (field: any) => {
    const fieldError = errors[field.name]
    
    switch (field.type) {
      case 'text':
      case 'ip':
      case 'url':
        return (
          <div key={field.name} className="space-y-2">
            <Label htmlFor={field.name}>
              {field.label}
              {field.required && <span className="text-red-500 ml-1">*</span>}
            </Label>
            <Input
              id={field.name}
              type="text"
              value={formData[field.name] || ''}
              onChange={(e) => setFormData({ ...formData, [field.name]: e.target.value })}
              placeholder={field.placeholder}
              className={fieldError ? 'border-red-500' : ''}
            />
            {fieldError && <p className="text-sm text-red-500">{fieldError}</p>}
          </div>
        )
      
      case 'number':
        return (
          <div key={field.name} className="space-y-2">
            <Label htmlFor={field.name}>
              {field.label}
              {field.required && <span className="text-red-500 ml-1">*</span>}
            </Label>
            <Input
              id={field.name}
              type="number"
              value={formData[field.name] || ''}
              onChange={(e) => setFormData({ ...formData, [field.name]: Number(e.target.value) })}
              min={field.min}
              max={field.max}
              step={field.step}
              className={fieldError ? 'border-red-500' : ''}
            />
            {fieldError && <p className="text-sm text-red-500">{fieldError}</p>}
          </div>
        )
      
      case 'select':
        return (
          <div key={field.name} className="space-y-2">
            <Label htmlFor={field.name}>
              {field.label}
              {field.required && <span className="text-red-500 ml-1">*</span>}
            </Label>
            <Select
              value={formData[field.name] || ''}
              onValueChange={(value) => setFormData({ ...formData, [field.name]: value })}
            >
              <SelectTrigger className={fieldError ? 'border-red-500' : ''}>
                <SelectValue placeholder={field.placeholder || t('Select...')} />
              </SelectTrigger>
              <SelectContent>
                {field.options?.map((option: any) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {fieldError && <p className="text-sm text-red-500">{fieldError}</p>}
          </div>
        )
      
      default:
        return null
    }
  }

  return (
    <div className="space-y-6">
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Device Configuration */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <BrandIcon integration={integration.name} className="w-6 h-6" size={24} />
              {t('Device Configuration')}
            </CardTitle>
            <CardDescription>
              {t('discovery.enter_device_details')}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {/* Basic Fields - IP and Name only */}
            {integration.manual_config?.fields
              .filter(field => field.name === 'ip' || field.name === 'name')
              .map(renderField)}
            
            {/* Advanced Settings Toggle */}
            {integration.manual_config?.fields && integration.manual_config.fields.filter(field => 
              field.name !== 'ip' && field.name !== 'name'
            ).length > 0 && (
              <div className="pt-4 border-t">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setShowAdvanced(!showAdvanced)}
                  className="w-full justify-between"
                >
                  <span>{t('discovery.advanced_settings')}</span>
                  {showAdvanced ? <ChevronUp /> : <ChevronDown />}
                </Button>
                
                {/* Advanced Fields */}
                {showAdvanced && (
                  <div className="space-y-4 mt-4">
                    {integration.manual_config?.fields
                      .filter(field => field.name !== 'ip' && field.name !== 'name')
                      .map(renderField)}
                  </div>
                )}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Auto Discovery Results */}
        {showDiscovery && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                {autoDiscovering ? <Loader2 className="w-4 h-4 animate-spin" /> : <Search className="w-4 h-4" />}
                {t('Device Discovery')}
              </CardTitle>
              <CardDescription>
                {autoDiscovering 
                  ? t('Searching for devices in your network...')
                  : t('Click on a discovered device to auto-fill the form')
                }
              </CardDescription>
            </CardHeader>
            <CardContent>
              {autoDiscovering ? (
                <div className="flex items-center justify-center py-8">
                  <div className="text-center">
                    <Loader2 className="w-8 h-8 animate-spin mx-auto mb-2" />
                    <p className="text-sm text-muted-foreground">{t('Scanning network...')}</p>
                  </div>
                </div>
              ) : discoveredDevices.length > 0 ? (
                <div className="space-y-2">
                  {discoveredDevices.map(device => (
                    <Card
                      key={device.id}
                      className="cursor-pointer hover:bg-muted/50 transition-colors"
                      onClick={() => handleDiscoveredDeviceSelect(device)}
                    >
                      <CardContent className="p-3">
                        <div className="flex items-center gap-3">
                          <Check className="w-4 h-4 text-green-500" />
                          <div className="flex-1">
                            <div className="font-medium">{device.name}</div>
                            <div className="text-sm text-muted-foreground">
                              IP: {device.ip} {device.model && `• Model: ${device.model}`}
                            </div>
                          </div>
                        </div>
                      </CardContent>
                    </Card>
                  ))}
                </div>
              ) : (
                <Alert>
                  <AlertCircle className="h-4 w-4" />
                  <AlertDescription>
                    {t('No devices found. Please enter device details manually.')}
                  </AlertDescription>
                </Alert>
              )}
            </CardContent>
          </Card>
        )}

        {/* Actions */}
        <div className="flex justify-end gap-2">
          <Button type="button" variant="outline" onClick={onCancel}>
            {t('Cancel')}
          </Button>
          <Button type="submit" disabled={saving}>
            {saving && <Loader2 className="w-4 h-4 mr-2 animate-spin" />}
            {t('Add Device')}
          </Button>
        </div>
      </form>
    </div>
  )
}