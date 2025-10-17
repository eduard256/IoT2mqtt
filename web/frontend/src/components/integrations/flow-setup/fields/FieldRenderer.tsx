import { Alert, AlertDescription } from '@/components/ui/alert'
import { fieldRegistry } from './registry'
import type { FormField } from '@/types/integration'

interface Props {
  field: FormField
  value: any
  onChange: (value: any) => void
  connectorName: string
  disabled?: boolean
  error?: string
}

export function FieldRenderer({ field, value, onChange, connectorName, disabled, error }: Props) {
  const fieldDef = fieldRegistry.getField(field.type, connectorName)

  if (!fieldDef) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Unknown field type: {field.type}</AlertDescription>
      </Alert>
    )
  }

  const FieldComponent = fieldDef.component

  return (
    <FieldComponent
      field={field}
      value={value}
      onChange={onChange}
      connectorName={connectorName}
      disabled={disabled}
      error={error}
    />
  )
}
