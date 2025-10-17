# Example: Simple Custom Field

This example shows how to create a basic custom field with validation.

## Color Picker Field

A simple color picker field for selecting colors.

### 1. Create Component

```typescript
// web/frontend/src/components/integrations/flow-setup/fields/custom/common/ColorPickerField.tsx
import { useState } from 'react'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import type { FieldComponentProps } from '../../../types'

export function ColorPickerField({ field, value, onChange, error }: FieldComponentProps<string>) {
  const [color, setColor] = useState(value ?? '#ffffff')

  const handleChange = (newColor: string) => {
    setColor(newColor)
    onChange(newColor)
  }

  return (
    <div className="space-y-2">
      <Label htmlFor={field.name}>
        {field.label ?? field.name}
        {field.required && <span className="text-destructive ml-1">*</span>}
      </Label>

      <div className="flex gap-2 items-center">
        <Input
          id={field.name}
          type="color"
          value={color}
          onChange={(e) => handleChange(e.target.value)}
          className="w-20 h-10"
        />
        <Input
          type="text"
          value={color}
          onChange={(e) => handleChange(e.target.value)}
          placeholder="#ffffff"
          className={error ? 'border-destructive' : ''}
        />
      </div>

      {field.description && (
        <p className="text-xs text-muted-foreground">{field.description}</p>
      )}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}
```

### 2. Register Field

```typescript
// web/frontend/src/components/integrations/flow-setup/fields/custom/common/index.ts
import { fieldRegistry } from '../../registry'
import { ColorPickerField } from './ColorPickerField'

fieldRegistry.registerCustom({
  type: 'color_picker',
  component: ColorPickerField,
  displayName: 'Color Picker',
  description: 'Select a color',
  validate: (value: string) => {
    if (!value) return null
    const regex = /^#[0-9A-F]{6}$/i
    return regex.test(value) ? null : 'Invalid color format (use #RRGGBB)'
  }
})
```

### 3. Use in setup.json

```json
{
  "flows": [{
    "id": "main",
    "name": "Setup",
    "steps": [{
      "id": "config",
      "type": "form",
      "title": "Configuration",
      "schema": {
        "fields": [
          {
            "type": "color_picker",
            "name": "default_color",
            "label": "Default Color",
            "description": "Select the default color for your lights",
            "required": true,
            "default": "#ffffff"
          }
        ]
      }
    }]
  }]
}
```

### Result

The user will see a color picker with both visual selector and text input for hex values.
