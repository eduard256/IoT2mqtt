import type { ChangeEvent } from 'react'
import { Textarea } from '@/components/ui/textarea'
import { Label } from '@/components/ui/label'
import type { FieldComponentProps } from '../../types'

export function TextareaField({ field, value, onChange, disabled, error }: FieldComponentProps<string>) {
  const handleChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    onChange(e.target.value)
  }

  return (
    <div className="space-y-2">
      <Label htmlFor={field.name}>
        {field.label ?? field.name}
        {field.required && <span className="text-destructive ml-1">*</span>}
      </Label>
      <Textarea
        id={field.name}
        placeholder={field.placeholder}
        value={value ?? ''}
        onChange={handleChange}
        disabled={disabled}
        rows={field.multiline ? 6 : 3}
        className={error ? 'border-destructive' : ''}
      />
      {field.description && (
        <p className="text-xs text-muted-foreground">{field.description}</p>
      )}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}
