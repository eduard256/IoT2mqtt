import { useState, useCallback, useMemo, useRef } from 'react'
import type { FlowState, FlowContext } from '../types'
import type { FlowDefinition, FormField } from '@/types/integration'

const initialFlowState: FlowState = {
  form: {},
  tools: {},
  selection: {},
  shared: {},
  oauth: {}
}

export function useFlowState(
  integration: { name: string; display_name?: string },
  currentFlow: FlowDefinition | undefined
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
  const buildContext = useCallback(
    (state: FlowState): FlowContext => {
      const enrichedForm: Record<string, any> = {}

      if (currentFlow) {
        for (const step of currentFlow.steps) {
          if (step.type === 'form' && step.id) {
            const formData = state.form[step.id] || {}
            const enrichedData: Record<string, any> = {}

            if (step.schema?.fields) {
              for (const field of step.schema.fields) {
                const currentValue = formData[field.name]
                const fieldExistsInFormData = field.name in formData

                if (fieldExistsInFormData) {
                  if (field.type === 'number' && typeof currentValue === 'string') {
                    const parsed = parseFloat(currentValue)
                    enrichedData[field.name] = isNaN(parsed) ? (field.default ?? 0) : parsed
                  } else {
                    enrichedData[field.name] = currentValue
                  }
                } else if (field.default !== undefined) {
                  enrichedData[field.name] = field.default
                }
              }
            }

            enrichedForm[step.id] = Object.keys(enrichedData).length > 0 ? enrichedData : formData
          } else if (state.form[step.id]) {
            enrichedForm[step.id] = state.form[step.id]
          }
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
    [integration, currentFlow]
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

        // Apply defaults for other fields
        const formStep = currentFlow?.steps.find(s => s.id === stepId && s.type === 'form')
        if (formStep?.schema?.fields) {
          for (const f of formStep.schema.fields) {
            if (f.name === field.name) continue
            if (!(f.name in updatedStepData) && f.default !== undefined) {
              updatedStepData[f.name] = f.default
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
    [currentFlow, updateFlowState]
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
