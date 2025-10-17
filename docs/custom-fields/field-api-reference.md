# Field API Reference

Complete API reference for creating custom fields.

## TypeScript Interfaces

### FieldComponentProps

Props passed to every field component.

```typescript
interface FieldComponentProps<T = any> {
  // Field configuration from setup.json
  field: FormField

  // Current value of the field
  value: T

  // Update the field value
  onChange: (value: T) => void

  // Is the field disabled?
  disabled?: boolean

  // Validation error message
  error?: string

  // Current connector name
  connectorName: string
}
```

### FormField

Field configuration object from setup.json.

```typescript
interface FormField {
  // Field type (e.g., 'text', 'number', 'custom_field')
  type: FormFieldType

  // Field name (used as key in form data)
  name: string

  // Human-readable label
  label?: string

  // Help text shown below field
  description?: string

  // Is this field required?
  required?: boolean

  // Default value
  default?: unknown

  // Placeholder text
  placeholder?: string

  // Options for select fields
  options?: FormFieldOption[]

  // Validation pattern (regex string)
  pattern?: string

  // Min value (for numbers)
  min?: number

  // Max value (for numbers)
  max?: number

  // Step value (for numbers)
  step?: number

  // Is this a multiline field?
  multiline?: boolean

  // Is this field a secret?
  secret?: boolean

  // Is this an advanced field? (hidden by default)
  advanced?: boolean

  // Visibility conditions
  conditions?: Record<string, unknown>

  // Custom configuration (resolved from templates)
  config?: Record<string, any>
}
```

### FieldDefinition

Definition for registering a field type.

```typescript
interface FieldDefinition {
  // Unique field type identifier
  type: string

  // React component for this field
  component: React.ComponentType<FieldComponentProps>

  // List of connectors this field is available for
  // If undefined, available for all connectors
  connectors?: string[]

  // Human-readable name
  displayName: string

  // Description of this field type
  description?: string

  // Optional validation function
  validate?: (value: any, field: FormField) => string | null
}
```

## Field Registry API

### registerStandard()

Register a standard field available for all connectors.

```typescript
fieldRegistry.registerStandard({
  type: 'my_field',
  component: MyFieldComponent,
  displayName: 'My Field',
  description: 'A standard field',
  validate: (value, field) => {
    if (!value && field.required) {
      return 'This field is required'
    }
    return null
  }
})
```

### registerCustom()

Register a custom field scoped to specific connectors.

```typescript
fieldRegistry.registerCustom({
  type: 'tuya_device_picker',
  component: TuyaDevicePicker,
  connectors: ['tuya', 'smart_life'],  // Only for these connectors
  displayName: 'Tuya Device Picker',
  description: 'Select devices from Tuya Cloud'
})
```

### getField()

Get a field definition by type and connector.

```typescript
const fieldDef = fieldRegistry.getField('tuya_device_picker', 'tuya')
if (fieldDef) {
  const Component = fieldDef.component
  // Render component
}
```

### getAvailableTypes()

Get all field types available for a connector.

```typescript
const types = fieldRegistry.getAvailableTypes('tuya')
// Returns: ['text', 'number', 'select', ..., 'tuya_device_picker', ...]
```

## Template Resolution

### Accessing Resolved Templates

In your field component, use `field.config` to access resolved template values:

```typescript
export function MyField({ field }: FieldComponentProps) {
  // These values have {{ }} templates already resolved
  const apiKey = field.config?.api_key
  const region = field.config?.region
  const userId = field.config?.user_id

  // Use them in your logic
  useEffect(() => {
    if (apiKey && region) {
      fetchData(apiKey, region)
    }
  }, [apiKey, region])
}
```

### Template Syntax in setup.json

```json
{
  "type": "my_custom_field",
  "name": "devices",
  "config": {
    "api_key": "{{ oauth.tuya.access_token }}",
    "region": "{{ form.region_step.region }}",
    "user_id": "{{ shared.user_id }}",
    "device_count": "{{ tools.discovery.device_count }}"
  }
}
```

### Available Context Paths

Templates can reference:

- `form.{step_id}.{field_name}` - Form field values
- `tools.{tool_name}.{property}` - Tool execution results
- `selection.{step_id}` - Selection step values
- `oauth.{provider}.{property}` - OAuth session data
- `shared.{key}` - Shared data across steps
- `integration.name` - Integration name
- `integration.display_name` - Integration display name

## Validation

### Field-level Validation

Implement validation in the field definition:

```typescript
fieldRegistry.registerCustom({
  type: 'ip_address',
  component: IpAddressField,
  displayName: 'IP Address',
  validate: (value: string, field: FormField) => {
    if (!value && field.required) {
      return `${field.label ?? field.name} is required`
    }

    if (value) {
      const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$/
      if (!ipRegex.test(value)) {
        return 'Invalid IP address format'
      }

      // Check octets are 0-255
      const octets = value.split('.').map(Number)
      if (octets.some(n => n > 255)) {
        return 'IP address octets must be 0-255'
      }
    }

    return null  // No error
  }
})
```

### Component-level Validation

Show validation errors in the component:

```typescript
export function MyField({ field, value, onChange, error }: FieldComponentProps) {
  const [localError, setLocalError] = useState<string | null>(null)

  const validateValue = (val: string) => {
    if (val.length < 3) {
      setLocalError('Must be at least 3 characters')
      return false
    }
    setLocalError(null)
    return true
  }

  const handleChange = (val: string) => {
    if (validateValue(val)) {
      onChange(val)
    }
  }

  const displayError = error || localError

  return (
    <div>
      <Input
        value={value}
        onChange={(e) => handleChange(e.target.value)}
        className={displayError ? 'border-destructive' : ''}
      />
      {displayError && (
        <p className="text-xs text-destructive">{displayError}</p>
      )}
    </div>
  )
}
```

## Hooks and Effects

### useEffect for Loading Data

```typescript
export function MyField({ field }: FieldComponentProps) {
  const [data, setData] = useState([])

  useEffect(() => {
    const loadData = async () => {
      const result = await fetchData()
      setData(result)
    }

    loadData()
  }, [])  // Run once on mount
}
```

### Cleanup

Always clean up subscriptions:

```typescript
useEffect(() => {
  const ws = new WebSocket('ws://...')

  ws.onmessage = (event) => {
    // Handle message
  }

  // Cleanup function
  return () => {
    ws.close()
  }
}, [])
```

### Debouncing

For search/filter fields:

```typescript
import { useEffect, useState } from 'react'

export function SearchField({ value, onChange }: FieldComponentProps<string>) {
  const [searchTerm, setSearchTerm] = useState(value ?? '')

  useEffect(() => {
    const timer = setTimeout(() => {
      onChange(searchTerm)
    }, 500)  // 500ms debounce

    return () => clearTimeout(timer)
  }, [searchTerm, onChange])

  return (
    <Input
      value={searchTerm}
      onChange={(e) => setSearchTerm(e.target.value)}
      placeholder="Search..."
    />
  )
}
```

## Error Handling

### Try-Catch Pattern

```typescript
const loadData = async () => {
  setLoading(true)
  setError(null)

  try {
    const response = await fetch('/api/data')
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }
    const data = await response.json()
    setData(data)
  } catch (e: any) {
    setError(e.message ?? 'Failed to load data')
    console.error('Error loading data:', e)
  } finally {
    setLoading(false)
  }
}
```

### Display Errors

```typescript
if (error) {
  return (
    <Alert variant="destructive">
      <AlertCircle className="h-4 w-4" />
      <AlertDescription>{error}</AlertDescription>
    </Alert>
  )
}
```

## Performance

### useMemo for Expensive Computations

```typescript
const filteredItems = useMemo(() => {
  return items.filter(item =>
    item.name.toLowerCase().includes(searchTerm.toLowerCase())
  )
}, [items, searchTerm])
```

### useCallback for Functions

```typescript
const handleSelect = useCallback((itemId: string) => {
  const selected = value ?? []
  const newValue = selected.includes(itemId)
    ? selected.filter(id => id !== itemId)
    : [...selected, itemId]
  onChange(newValue)
}, [value, onChange])
```

## UI Components

Use existing UI components for consistency:

```typescript
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Badge } from '@/components/ui/badge'
import { Checkbox } from '@/components/ui/checkbox'
```

See [shadcn/ui documentation](https://ui.shadcn.com/) for component usage.
