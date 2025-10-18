import { useState, useCallback, useMemo, useRef } from 'react'
import type { FlowState, FlowContext } from '../types'
import type { FlowSetupSchema, FormField } from '@/types/integration'

const initialFlowState: FlowState = {
  form: {},
  tools: {},
  selection: {},
  shared: {},
  oauth: {}
}

export function useFlowState(
  integration: { name: string; display_name?: string },
  schema: FlowSetupSchema | null
) {
  const [flowState, setFlowState] = useState<FlowState>(initialFlowState)
  const flowStateRef = useRef<FlowState>(initialFlowState)

  // Keep ref in sync
  const updateFlowState = useCallback((updater: (prev: FlowState) => FlowState) => {
    setFlowState(prev => {
      const newState = updater(prev)
      flowStateRef.current = newState
      return newState
    })
  }, [])

  // Build context with defaults applied
  // This processes ALL form data in flowState, regardless of which flow is active
  const buildContext = useCallback(
    (state: FlowState): FlowContext => {
      const enrichedForm: Record<string, any> = {}

      // Build a map of all form steps from all flows in schema
      const formStepsMap = new Map<string, any>()

      if (schema?.flows) {
        for (const flow of schema.flows) {
          for (const step of flow.steps) {
            if (step.type === 'form' && step.id) {
              formStepsMap.set(step.id, step)
            }
          }
        }
      }

      // Process all form data in flowState
      for (const [stepId, formData] of Object.entries(state.form)) {
        const step = formStepsMap.get(stepId)

        if (step?.schema?.fields) {
          // Apply defaults and type conversions
          const enrichedData: Record<string, any> = {}

          for (const field of step.schema.fields) {
            const currentValue = formData[field.name]
            const fieldExistsInFormData = field.name in formData

            if (fieldExistsInFormData) {
              // Type conversion for number fields
              if (field.type === 'number' && typeof currentValue === 'string') {
                const parsed = parseFloat(currentValue)
                enrichedData[field.name] = isNaN(parsed) ? (field.default ?? 0) : parsed
              } else {
                enrichedData[field.name] = currentValue
              }
            } else if (field.default !== undefined) {
              // Apply default value if field is not present
              enrichedData[field.name] = field.default
            }
          }

          enrichedForm[stepId] = Object.keys(enrichedData).length > 0 ? enrichedData : formData
        } else {
          // Step not found in schema or has no fields - use data as-is
          enrichedForm[stepId] = formData
        }
      }

      return {
        integration,
        form: enrichedForm,
        tools: state.tools,
        selection: state.selection,
        shared: state.shared,
        oauth: state.oauth
      }
    },
    [integration, schema]
  )

  const context = useMemo(() => buildContext(flowState), [buildContext, flowState])

  const updateFormValue = useCallback(
    (stepId: string, field: FormField, value: any) => {
      updateFlowState(prev => {
        const currentStepData = prev.form[stepId] ?? {}
        const updatedStepData = {
          ...currentStepData,
          [field.name]: value
        }

        // Apply defaults for other fields in the same step
        if (schema?.flows) {
          for (const flow of schema.flows) {
            const formStep = flow.steps.find(s => s.id === stepId && s.type === 'form')
            if (formStep?.schema?.fields) {
              for (const f of formStep.schema.fields) {
                if (f.name === field.name) continue
                if (!(f.name in updatedStepData) && f.default !== undefined) {
                  updatedStepData[f.name] = f.default
                }
              }
              break
            }
          }
        }

        return {
          ...prev,
          form: {
            ...prev.form,
            [stepId]: updatedStepData
          }
        }
      })
    },
    [schema, updateFlowState]
  )

  const resetFlowState = useCallback(() => {
    setFlowState(initialFlowState)
    flowStateRef.current = initialFlowState
  }, [])

  return {
    flowState,
    flowStateRef,
    updateFlowState,
    context,
    buildContext,
    updateFormValue,
    resetFlowState
  }
}
