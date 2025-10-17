import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import type { FieldComponentProps } from '../../types'

export function SelectField({ field, value, onChange, disabled, error }: FieldComponentProps<string>) {
  return (
    <div className="space-y-2">
      <Label htmlFor={field.name}>
        {field.label ?? field.name}
        {field.required && <span className="text-destructive ml-1">*</span>}
      </Label>
      <Select value={value} onValueChange={onChange} disabled={disabled}>
        <SelectTrigger className={error ? 'border-destructive' : ''}>
          <SelectValue placeholder={field.placeholder ?? 'Select option'} />
        </SelectTrigger>
        <SelectContent>
          {(field.options ?? []).map(option => (
            <SelectItem key={option.value} value={option.value}>
              {option.label}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {field.description && (
        <p className="text-xs text-muted-foreground">{field.description}</p>
      )}
      {error && <p className="text-xs text-destructive">{error}</p>}
    </div>
  )
}
