# Custom Fields System

## Overview

The FlowSetupForm uses a **plugin-based architecture** that allows you to create custom form fields with any level of complexity. Custom fields are React components that can contain any logic: API calls, WebSocket connections, SSE streams, complex state management, and more.

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Creating Custom Fields](#creating-custom-fields)
- [Standard Fields](#standard-fields)
- [Custom Steps](#custom-steps)
- [API Reference](#api-reference)
- [Examples](#examples)

## Quick Start

### 1. Create a Custom Field Component

```typescript
// web/frontend/src/components/integrations/flow-setup/fields/custom/tuya/TuyaDevicePicker.tsx
import { useState, useEffect } from 'react'
import type { FieldComponentProps } from '../../../types'

export function TuyaDevicePicker({ field, value, onChange }: FieldComponentProps<string[]>) {
  const [devices, setDevices] = useState([])
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    // Your complex logic here - API calls, WebSocket, SSE, etc.
    fetchDevices()
  }, [])

  return (
    <div>
      {/* Your custom UI */}
    </div>
  )
}
```

### 2. Register Your Field

```typescript
// web/frontend/src/components/integrations/flow-setup/fields/custom/tuya/index.ts
import { fieldRegistry } from '../../registry'
import { TuyaDevicePicker } from './TuyaDevicePicker'

fieldRegistry.registerCustom({
  type: 'tuya_device_picker',
  component: TuyaDevicePicker,
  connectors: ['tuya'],  // Only available for Tuya connector
  displayName: 'Tuya Device Picker',
  description: 'Select devices from Tuya Cloud account'
})
```

### 3. Import Registration in Main App

```typescript
// web/frontend/src/components/integrations/flow-setup/fields/custom/index.ts
import './tuya'
import './yeelight'
import './xiaomi'
// ... other custom field registrations
```

### 4. Use in setup.json

```json
{
  "flows": [{
    "steps": [{
      "type": "form",
      "schema": {
        "fields": [
          {
            "type": "tuya_device_picker",
            "name": "devices",
            "label": "Select Devices",
            "required": true
          }
        ]
      }
    }]
  }]
}
```

## Architecture

### Directory Structure

```
flow-setup/
├── types.ts                        # TypeScript interfaces
├── fields/
│   ├── registry.ts                 # Field Registry (singleton)
│   ├── FieldRenderer.tsx           # Main renderer - selects field from registry
│   ├── standard/                   # Built-in fields (text, number, etc.)
│   │   ├── TextField.tsx
│   │   ├── NumberField.tsx
│   │   ├── SelectField.tsx
│   │   └── ...
│   └── custom/                     # Custom fields per connector
│       ├── tuya/
│       │   ├── TuyaDevicePicker.tsx
│       │   ├── TuyaRegionSelector.tsx
│       │   └── index.ts
│       ├── yeelight/
│       │   └── ...
│       └── index.ts
├── steps/                          # Step components (form, tool, oauth, etc.)
├── hooks/                          # Reusable hooks
└── utils/                          # Utility functions
```

### How It Works

1. **Field Registry** - A singleton Map that stores all available field types
2. **FieldRenderer** - Looks up the field type in registry and renders the component
3. **Custom vs Standard** - Custom fields have higher priority than standard fields
4. **Connector Scoping** - Fields can be scoped to specific connectors

## Creating Custom Fields

### Field Component Props

Every field component receives these props:

```typescript
interface FieldComponentProps<T = any> {
  field: FormField            // Field configuration from setup.json
  value: T                    // Current value
  onChange: (value: T) => void  // Update value
  disabled?: boolean          // Is field disabled
  error?: string             // Validation error
  connectorName: string      // Current connector name
}
```

### Example: Simple Custom Field

```typescript
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import type { FieldComponentProps } from '../../types'

export function IpAddressField({ field, value, onChange, error }: FieldComponentProps<string>) {
  const validateIP = (ip: string) => {
    const regex = /^(\d{1,3}\.){3}\d{1,3}$/
    return regex.test(ip)
  }

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newValue = e.target.value
    onChange(newValue)
  }

  return (
    <div className="space-y-2">
      <Label>{field.label ?? field.name}</Label>
      <Input
        type="text"
        placeholder={field.placeholder ?? "192.168.1.1"}
        value={value ?? ''}
        onChange={handleChange}
        className={error ? 'border-destructive' : ''}
      />
      {!validateIP(value) && value && (
        <p className="text-xs text-destructive">Invalid IP address</p>
      )}
      {field.description && (
        <p className="text-xs text-muted-foreground">{field.description}</p>
      )}
    </div>
  )
}
```

### Example: Complex Custom Field with API

```typescript
import { useState, useEffect } from 'react'
import { Loader2 } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { getAuthToken } from '@/utils/auth'
import type { FieldComponentProps } from '../../types'

interface Device {
  id: string
  name: string
  online: boolean
}

export function TuyaDevicePicker({ field, value, onChange }: FieldComponentProps<string[]>) {
  const [devices, setDevices] = useState<Device[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadDevices()
  }, [])

  const loadDevices = async () => {
    setLoading(true)
    setError(null)
    try {
      // Access field.config for resolved template values
      const apiKey = field.config?.api_key
      const region = field.config?.region

      const token = getAuthToken()
      const response = await fetch(`/api/integrations/tuya/devices`, {
        headers: {
          Authorization: `Bearer ${token}`,
          'X-Tuya-Region': region
        }
      })

      if (!response.ok) throw new Error('Failed to load devices')

      const data = await response.json()
      setDevices(data.devices)
    } catch (e: any) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  const toggleDevice = (deviceId: string) => {
    const selected = value ?? []
    const newValue = selected.includes(deviceId)
      ? selected.filter(id => id !== deviceId)
      : [...selected, deviceId]
    onChange(newValue)
  }

  if (loading) {
    return (
      <div className="flex items-center gap-2">
        <Loader2 className="h-4 w-4 animate-spin" />
        <span>Loading devices...</span>
      </div>
    )
  }

  if (error) {
    return <div className="text-destructive">{error}</div>
  }

  return (
    <div className="space-y-2">
      <Label>{field.label ?? 'Select Devices'}</Label>
      <div className="space-y-2">
        {devices.map(device => {
          const isSelected = (value ?? []).includes(device.id)
          return (
            <Card
              key={device.id}
              className={`cursor-pointer ${isSelected ? 'border-primary' : ''}`}
              onClick={() => toggleDevice(device.id)}
            >
              <CardContent className="p-3">
                <div className="flex justify-between items-center">
                  <span>{device.name}</span>
                  <Badge variant={device.online ? 'success' : 'secondary'}>
                    {device.online ? 'Online' : 'Offline'}
                  </Badge>
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>
    </div>
  )
}
```

### Example: WebSocket Field

```typescript
import { useState, useEffect, useRef } from 'react'
import type { FieldComponentProps } from '../../types'

export function LiveDataField({ field, value, onChange }: FieldComponentProps<any>) {
  const [data, setData] = useState<any>(null)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {
    // Connect to WebSocket
    const ws = new WebSocket('ws://localhost:8080/live-data')
    wsRef.current = ws

    ws.onmessage = (event) => {
      const newData = JSON.parse(event.data)
      setData(newData)
      onChange(newData)
    }

    ws.onerror = (error) => {
      console.error('WebSocket error:', error)
    }

    return () => {
      ws.close()
    }
  }, [])

  return (
    <div>
      <h3>Live Data</h3>
      <pre>{JSON.stringify(data, null, 2)}</pre>
    </div>
  )
}
```

## Standard Fields

Built-in field types available by default:

| Type | Component | Description |
|------|-----------|-------------|
| `text` | TextField | Single-line text input |
| `number` | NumberField | Numeric input with min/max |
| `password` | PasswordField | Masked text input |
| `select` | SelectField | Dropdown selection |
| `checkbox` | CheckboxField | Boolean checkbox |
| `textarea` | TextareaField | Multi-line text input |
| `ip` | TextField | IP address (alias for text) |
| `url` | TextField | URL (alias for text) |
| `email` | TextField | Email (alias for text) |

## Custom Steps

You can also create custom step types (not just fields):

```typescript
// web/frontend/src/components/integrations/flow-setup/steps/CustomStep/CustomStep.tsx
import type { StepComponentProps } from '../../types'

export function CustomStep({ step, flowState, updateFlowState }: StepComponentProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{step.title}</CardTitle>
      </CardHeader>
      <CardContent>
        {/* Your custom step UI */}
      </CardContent>
    </Card>
  )
}

// Register it
stepRegistry.register({
  type: 'custom_step',
  component: CustomStep,
  displayName: 'Custom Step',
  description: 'A custom flow step'
})
```

## API Reference

### Field Registry

```typescript
class FieldRegistry {
  // Register a standard field (available for all connectors)
  registerStandard(definition: FieldDefinition): void

  // Register a custom field (scoped to specific connectors)
  registerCustom(definition: FieldDefinition): void

  // Get field definition by type
  getField(type: string, connectorName?: string): FieldDefinition | null

  // Get all available field types for a connector
  getAvailableTypes(connectorName?: string): string[]
}
```

### Field Definition

```typescript
interface FieldDefinition {
  type: string                                      // Unique field type
  component: React.ComponentType<FieldComponentProps>  // React component
  connectors?: string[]                             // Connector whitelist
  displayName: string                               // Human-readable name
  description?: string                              // Description
  validate?: (value: any, field: FormField) => string | null  // Validator
}
```

### Accessing Configuration

In your custom field, you can access resolved template values via `field.config`:

```typescript
export function MyField({ field, value, onChange }: FieldComponentProps) {
  // field.config contains resolved {{ }} templates from setup.json
  const apiKey = field.config?.api_key
  const region = field.config?.region

  // Use these values in your logic
}
```

### setup.json Configuration

```json
{
  "type": "my_custom_field",
  "name": "field_name",
  "label": "Field Label",
  "description": "Help text",
  "required": true,
  "default": "default value",
  "config": {
    "api_key": "{{ oauth.provider.access_token }}",
    "region": "{{ form.region_step.region }}"
  }
}
```

## Best Practices

1. **Error Handling** - Always handle errors gracefully
2. **Loading States** - Show loading indicators for async operations
3. **Cleanup** - Clean up subscriptions (WebSocket, SSE) in useEffect cleanup
4. **TypeScript** - Use proper types for `value` in `FieldComponentProps<T>`
5. **Accessibility** - Use semantic HTML and proper labels
6. **Validation** - Implement validation and show clear error messages
7. **Performance** - Memoize expensive computations with `useMemo`

## Troubleshooting

### Field Not Showing

1. Check that the field is registered before the form renders
2. Verify the `type` in setup.json matches the registered type
3. Check `connectors` array includes the current connector
4. Look for errors in browser console

### Templates Not Resolving

- Ensure the field has access to `field.config`
- Check that templates reference valid paths (e.g., `form.step_id.field_name`)
- Verify the dependency steps have run before your field

### Styling Issues

- Use Tailwind classes for consistency
- Import UI components from `@/components/ui/*`
- Follow existing field components for examples

## Examples Directory

See `docs/custom-fields/examples/` for complete working examples:

- [Simple Custom Field](examples/simple-custom-field.md)
- [API-based Field](examples/api-field.md)
- [WebSocket Field](examples/websocket-field.md)
- [Multi-step Field](examples/complex-validation.md)
