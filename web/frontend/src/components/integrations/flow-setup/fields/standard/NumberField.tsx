import type { ChangeEvent } from 'react'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import type { FieldComponentProps } from '../../types'

export function NumberField({ field, value, onChange, disabled, error }: FieldComponentProps<number>) {
  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    const val = e.target.value
    const numValue = val === '' ? '' : parseFloat(val)
    onChange(isNaN(numValue as number) ? '' : (numValue as any))
  }

  return (
    <div className="space-y-2">
      <Label htmlFor={field.name}>
        {field.label ?? field.name}
        {field.required && <span className="text-destructive ml-1">*</span>}
      </Label>
      <Input
        id={field.name}
        type="number"
        placeholder={field.placeholder ?? field.default?.toString()}
        value={value ?? ''}
        min={field.min}
        max={field.max}
        step={field.step}
        onChange={handleChange}
        disabled={disabled}
        className={error ? 'border-destructive' : ''}
      />
      {field.description && (
        <p className="text-xs text-muted-foreground">{field.description}</p>
      )}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}
