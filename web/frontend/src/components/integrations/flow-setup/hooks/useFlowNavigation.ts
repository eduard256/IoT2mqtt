import { useState, useMemo, useEffect, useCallback, useRef } from 'react'
import type { FlowDefinition, FlowStep, FlowSetupSchema } from '@/types/integration'
import type { FlowState } from '../types'
import { evaluateConditions } from '../utils/conditionEvaluator'

export function useFlowNavigation(
  schema: FlowSetupSchema | null,
  flowState: FlowState,
  context: any,
  resolveTemplate: (value: unknown) => any
) {
  const [currentFlowId, setCurrentFlowId] = useState<string | null>(null)
  const [currentStepIndex, setCurrentStepIndex] = useState(0)
  const autoRanSteps = useRef<Set<string>>(new Set())

  // Initialize flow
  useEffect(() => {
    if (schema && !currentFlowId) {
      const defaultFlow = schema.flows.find(flow => flow.default) ?? schema.flows[0]
      setCurrentFlowId(defaultFlow?.id || null)
    }
  }, [schema, currentFlowId])

  const currentFlow = useMemo<FlowDefinition | undefined>(() => {
    if (!schema || !currentFlowId) return undefined
    return schema.flows.find(flow => flow.id === currentFlowId) ?? schema.flows[0]
  }, [schema, currentFlowId])

  const visibleSteps = useMemo<FlowStep[]>(() => {
    if (!currentFlow) return []

    return currentFlow.steps.filter(step => {
      // Check visibility conditions
      if (!evaluateConditions(step.conditions, context, resolveTemplate)) return false

      // Hide tool steps with auto_advance that completed successfully
      if (step.type === 'tool' && step.auto_advance) {
        const storageKey = step.output_key ?? step.tool ?? step.id
        const result = flowState.tools[storageKey]
        if (result && result.ok === true) {
          return false
        }
      }

      // Hide summary steps (shown inside instance step)
      if (step.type === 'summary') {
        return false
      }

      return true
    })
  }, [currentFlow, flowState, context, resolveTemplate])

  // Adjust index if out of bounds
  useEffect(() => {
    if (currentStepIndex >= visibleSteps.length && visibleSteps.length > 0) {
      setCurrentStepIndex(visibleSteps.length - 1)
    }
  }, [visibleSteps, currentStepIndex])

  const currentStep = visibleSteps[currentStepIndex] || null

  const goToFlow = useCallback((flowId: string) => {
    setCurrentFlowId(flowId)
    setCurrentStepIndex(0)
    autoRanSteps.current = new Set()
  }, [])

  const advanceStep = useCallback((delta: number) => {
    setCurrentStepIndex(prev => {
      const nextIndex = Math.max(0, Math.min(prev + delta, visibleSteps.length - 1))
      return nextIndex
    })
  }, [visibleSteps])

  const goToStepById = useCallback(
    (stepId: string) => {
      const index = visibleSteps.findIndex(s => s.id === stepId)
      if (index !== -1) {
        setCurrentStepIndex(index)
      }
    },
    [visibleSteps]
  )

  return {
    currentFlow,
    currentFlowId,
    currentStep,
    currentStepIndex,
    visibleSteps,
    autoRanSteps,
    setCurrentFlowId,
    setCurrentStepIndex,
    goToFlow,
    advanceStep,
    goToStepById
  }
}
