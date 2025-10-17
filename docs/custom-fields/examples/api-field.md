# Example: API-based Custom Field

This example demonstrates creating a field that fetches data from an API and lets users select from the results.

## Region Selector with API

A field that loads available regions from an API and displays them as cards.

### 1. Create Component

```typescript
// web/frontend/src/components/integrations/flow-setup/fields/custom/tuya/RegionSelector.tsx
import { useState, useEffect } from 'react'
import { Loader2, Globe } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { getAuthToken } from '@/utils/auth'
import { cn } from '@/lib/utils'
import type { FieldComponentProps } from '../../../types'

interface Region {
  code: string
  name: string
  endpoint: string
}

export function RegionSelector({ field, value, onChange }: FieldComponentProps<string>) {
  const [regions, setRegions] = useState<Region[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadRegions()
  }, [])

  const loadRegions = async () => {
    setLoading(true)
    setError(null)

    try {
      const token = getAuthToken()
      const response = await fetch('/api/integrations/tuya/regions', {
        headers: { Authorization: `Bearer ${token}` }
      })

      if (!response.ok) {
        throw new Error(`Failed to load regions: ${response.statusText}`)
      }

      const data = await response.json()
      setRegions(data.regions)
    } catch (e: any) {
      setError(e.message ?? 'Failed to load regions')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="space-y-2">
        <Label>{field.label ?? 'Region'}</Label>
        <div className="flex items-center gap-2 p-4 border rounded">
          <Loader2 className="h-4 w-4 animate-spin" />
          <span className="text-sm text-muted-foreground">Loading regions...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="space-y-2">
        <Label>{field.label ?? 'Region'}</Label>
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      </div>
    )
  }

  return (
    <div className="space-y-2">
      <Label>
        {field.label ?? 'Region'}
        {field.required && <span className="text-destructive ml-1">*</span>}
      </Label>

      <div className="grid grid-cols-2 gap-2">
        {regions.map(region => {
          const isSelected = value === region.code

          return (
            <Card
              key={region.code}
              className={cn(
                'cursor-pointer transition-all hover:shadow-md',
                isSelected ? 'border-primary bg-primary/5' : 'border-border'
              )}
              onClick={() => onChange(region.code)}
            >
              <CardContent className="p-4">
                <div className="flex items-start gap-3">
                  <Globe className={cn(
                    'h-5 w-5 mt-0.5',
                    isSelected ? 'text-primary' : 'text-muted-foreground'
                  )} />
                  <div className="flex-1">
                    <div className="font-medium">{region.name}</div>
                    <div className="text-xs text-muted-foreground">{region.code}</div>
                    <div className="text-xs text-muted-foreground mt-1">{region.endpoint}</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          )
        })}
      </div>

      {field.description && (
        <p className="text-xs text-muted-foreground">{field.description}</p>
      )}
    </div>
  )
}
```

### 2. Register Field

```typescript
// web/frontend/src/components/integrations/flow-setup/fields/custom/tuya/index.ts
import { fieldRegistry } from '../../registry'
import { RegionSelector } from './RegionSelector'

fieldRegistry.registerCustom({
  type: 'tuya_region_selector',
  component: RegionSelector,
  connectors: ['tuya'],
  displayName: 'Tuya Region Selector',
  description: 'Select Tuya Cloud region'
})
```

### 3. Backend API Endpoint

```python
# Example backend endpoint (FastAPI)
@router.get('/integrations/tuya/regions')
async def get_tuya_regions(current_user: User = Depends(get_current_user)):
    regions = [
        {"code": "us", "name": "Americas", "endpoint": "https://openapi.tuyaus.com"},
        {"code": "eu", "name": "Europe", "endpoint": "https://openapi.tuyaeu.com"},
        {"code": "cn", "name": "China", "endpoint": "https://openapi.tuyacn.com"},
        {"code": "in", "name": "India", "endpoint": "https://openapi.tuyain.com"}
    ]
    return {"regions": regions}
```

### 4. Use in setup.json

```json
{
  "flows": [{
    "id": "main",
    "name": "Setup Tuya",
    "steps": [{
      "id": "region_step",
      "type": "form",
      "title": "Select Region",
      "schema": {
        "fields": [
          {
            "type": "tuya_region_selector",
            "name": "region",
            "label": "Tuya Cloud Region",
            "description": "Select the region where your Tuya account is registered",
            "required": true
          }
        ]
      }
    }]
  }]
}
```

### Key Features

- **Async Loading**: Shows loading state while fetching data
- **Error Handling**: Displays error messages if API call fails
- **Visual Selection**: Card-based UI for easy selection
- **Responsive**: Grid layout adapts to screen size
- **Scoped**: Only available for Tuya connector

### Advanced: Using Cached Data

You can cache the API response to avoid repeated calls:

```typescript
const CACHE_KEY = 'tuya_regions'
const CACHE_DURATION = 5 * 60 * 1000 // 5 minutes

useEffect(() => {
  const cached = localStorage.getItem(CACHE_KEY)
  if (cached) {
    const { data, timestamp } = JSON.parse(cached)
    if (Date.now() - timestamp < CACHE_DURATION) {
      setRegions(data)
      setLoading(false)
      return
    }
  }
  loadRegions()
}, [])

const loadRegions = async () => {
  // ... fetch logic ...
  localStorage.setItem(CACHE_KEY, JSON.stringify({
    data: data.regions,
    timestamp: Date.now()
  }))
}
```
