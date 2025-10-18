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

  // Resolve templates in all field configs (must be outside map for React hooks rules)
  const resolvedFields = useMemo(() => {
    console.log('━'.repeat(80))
    console.log('[FormStep] Step ID:', step.id)
    console.log('[FormStep] Step title:', step.title)
    console.log('[FormStep] RAW step.schema:', step.schema)
    console.log('[FormStep] RAW step.schema.fields:', step.schema?.fields)
    console.log('[FormStep] Number of fields:', step.schema?.fields?.length ?? 0)

    // Log each field in detail
    step.schema?.fields?.forEach((field, idx) => {
      console.log(`[FormStep] Field ${idx}:`, {
        name: field.name,
        type: field.type,
        label: field.label,
        hasConfig: !!field.config,
        config: field.config,
        allKeys: Object.keys(field)
      })
    })

    console.log('[FormStep] Context.form FULL:', JSON.stringify(context.form, null, 2))
    console.log('[FormStep] FlowState.form FULL:', JSON.stringify(flowState.form, null, 2))
    console.log('[FormStep] Context.form.camera_form:', context.form?.camera_form)
    console.log('[FormStep] Context.form.network_form:', context.form?.network_form)

    const result = step.schema?.fields?.map(field => {
      if (!field.config) {
        console.log(`[FormStep] Field "${field.name}" has NO config, skipping`)
        return field
      }

      console.log(`[FormStep] Field "${field.name}" HAS config:`, field.config)
      const resolved = resolveDeep(field.config)
      console.log(`[FormStep] Field "${field.name}" resolved to:`, resolved)

      return {
        ...field,
        config: resolved
      }
    }) ?? []

    console.log('[FormStep] Final resolved fields:', result)
    console.log('━'.repeat(80))
    return result
  }, [step.schema?.fields, resolveDeep, context, flowState])

  return (
    <Card>
      <CardHeader>
        <CardTitle>{step.title ?? 'Configuration'}</CardTitle>
        {step.description && <CardDescription>{step.description}</CardDescription>}
      </CardHeader>
      <CardContent className="space-y-4">
        {resolvedFields.map(field => {
          // Check visibility conditions
          if (!evaluateConditions(field.conditions, context, v => v)) return null
          if (field.advanced && !showAdvanced) return null

          const value = flowState.form[step.id]?.[field.name] ?? field.default ?? ''

          return (
            <FieldRenderer
              key={field.name}
              field={field}
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
