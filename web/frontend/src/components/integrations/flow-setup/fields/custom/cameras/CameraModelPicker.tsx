import { useState, useEffect, useRef } from 'react'
import { Label } from '@/components/ui/label'
import { Input } from '@/components/ui/input'
import { Card } from '@/components/ui/card'
import { Loader2 } from 'lucide-react'
import { getAuthToken } from '@/utils/auth'
import type { FieldComponentProps } from '../../../types'

interface CameraModel {
  brand: string
  brand_id: string
  model: string
  display: string
  entry: any
}

export function CameraModelPicker({ field, value, onChange, error }: FieldComponentProps<string>) {
  const [query, setQuery] = useState(value || '')
  const [results, setResults] = useState<CameraModel[]>([])
  const [isOpen, setIsOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const [justSelected, setJustSelected] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  // Debounced search
  useEffect(() => {
    if (query.length < 2) {
      setResults([])
      setIsOpen(false)
      return
    }

    // Don't search or open dropdown if user just selected a model
    if (justSelected) {
      return
    }

    const timer = setTimeout(async () => {
      setLoading(true)
      try {
        const token = getAuthToken()
        const res = await fetch(`/api/cameras/search?q=${encodeURIComponent(query)}&limit=50`, {
          headers: {
            Authorization: `Bearer ${token}`
          }
        })

        if (!res.ok) {
          throw new Error('Search failed')
        }

        const data = await res.json()
        setResults(data.results || [])
        // Only open if we have results and it wasn't just a selection
        if (data.results?.length > 0 && !justSelected) {
          setIsOpen(true)
        }
      } catch (err) {
        setResults([])
        setIsOpen(false)
      } finally {
        setLoading(false)
      }
    }, 300)

    return () => clearTimeout(timer)
  }, [query, justSelected])

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleSelect = (item: CameraModel) => {
    // Save full model data as JSON string
    const modelData = JSON.stringify({
      brand: item.brand,
      brand_id: item.brand_id,
      model: item.model,
      display: item.display
    })

    onChange(modelData)
    setQuery(item.display)
    setIsOpen(false)
    setJustSelected(true)
  }

  return (
    <div ref={containerRef} className="relative space-y-2">
      <Label>
        {field.label ?? field.name}
        {field.required && <span className="text-destructive ml-1">*</span>}
      </Label>

      <div className="relative">
        <Input
          type="text"
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            // Reset justSelected flag when user starts typing
            setJustSelected(false)
          }}
          onFocus={() => {
            // Only open dropdown if there are results and user hasn't just selected
            if (results.length > 0 && !justSelected) {
              setIsOpen(true)
            }
          }}
          placeholder={field.placeholder ?? "Start typing..."}
          className={error ? 'border-destructive' : ''}
        />

        {loading && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">
            <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
          </div>
        )}
      </div>

      {field.description && (
        <p className="text-xs text-muted-foreground">{field.description}</p>
      )}

      {error && (
        <p className="text-xs text-destructive">{error}</p>
      )}

      {/* Dropdown overlay */}
      {isOpen && results.length > 0 && (
        <Card className="absolute z-50 w-full mt-1 max-h-64 overflow-auto shadow-lg border bg-popover">
          <div className="p-1">
            {results.map((item, index) => (
              <div
                key={`${item.brand_id}-${item.model}-${index}`}
                className="px-3 py-2 hover:bg-accent rounded-sm cursor-pointer transition-colors"
                onClick={() => handleSelect(item)}
              >
                <div className="text-sm font-medium">{item.display}</div>
              </div>
            ))}
          </div>
        </Card>
      )}
    </div>
  )
}
