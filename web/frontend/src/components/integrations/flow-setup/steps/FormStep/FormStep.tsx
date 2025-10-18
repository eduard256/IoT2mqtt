import { useState, useMemo } from 'react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { FieldRenderer } from '../../fields/FieldRenderer'
import { evaluateConditions } from '../../utils/conditionEvaluator'
import { useTemplateResolver } from '../../hooks/useTemplateResolver'
import type { StepComponentProps } from '../../types'
import type { FormField } from '@/types/integration'

export function FormStep({
  step,
  flowState,
  updateFlowState,
  context,
  connectorName
}: StepComponentProps) {
  const [showAdvanced, setShowAdvanced] = useState(false)
  const { resolveDeep } = useTemplateResolver(context)

  const updateFormValue = (fieldName: string, value: any) => {
    updateFlowState(prev => ({
      ...prev,
      form: {
        ...prev.form,
        [step.id]: {
          ...prev.form[step.id],
          [fieldName]: value
        }
      }
    }))
  }

  const hasAdvancedFields = step.schema?.fields?.some(field => field.advanced) ?? false

  return (
    <Card>
      <CardHeader>
        <CardTitle>{step.title ?? 'Configuration'}</CardTitle>
        {step.description && <CardDescription>{step.description}</CardDescription>}
      </CardHeader>
      <CardContent className="space-y-4">
        {step.schema?.fields?.map(field => {
          // Check visibility conditions
          if (!evaluateConditions(field.conditions, context, v => v)) return null
          if (field.advanced && !showAdvanced) return null

          const value = flowState.form[step.id]?.[field.name] ?? field.default ?? ''

          // Resolve templates in field.config if present
          const resolvedField: FormField = useMemo(() => {
            if (!field.config) return field

            return {
              ...field,
              config: resolveDeep(field.config)
            }
          }, [field, context])

          return (
            <FieldRenderer
              key={field.name}
              field={resolvedField}
              value={value}
              onChange={val => updateFormValue(field.name, val)}
              connectorName={connectorName}
            />
          )
        })}

        {hasAdvancedFields && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className="w-full"
          >
            {showAdvanced ? 'Hide Advanced' : 'Show Advanced'}
          </Button>
        )}
      </CardContent>
    </Card>
  )
}
