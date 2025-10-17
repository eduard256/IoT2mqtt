import { Checkbox } from '@/components/ui/checkbox'
import { Label } from '@/components/ui/label'
import type { FieldComponentProps } from '../../types'

export function CheckboxField({ field, value, onChange, disabled }: FieldComponentProps<boolean>) {
  return (
    <div className="flex items-center space-x-2">
      <Checkbox
        id={field.name}
        checked={Boolean(value)}
        onCheckedChange={onChange}
        disabled={disabled}
      />
      <Label htmlFor={field.name} className="font-normal cursor-pointer">
        {field.label ?? field.name}
      </Label>
      {field.description && (
        <p className="text-xs text-muted-foreground ml-6">{field.description}</p>
      )}
    </div>
  )
}
