import { useEffect, useState, useCallback, useRef } from 'react'
import { Loader2, ExternalLink } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { getAuthToken } from '@/utils/auth'
import type { FlowSetupSchema, FlowAction, FlowStep } from '@/types/integration'

// Import registries and registration functions
import { registerStandardFields } from './flow-setup/fields/standard'
import { registerStandardSteps, stepRegistry } from './flow-setup/steps'
import './flow-setup/fields/custom'  // Register custom fields

// Import hooks
import { useFlowState } from './flow-setup/hooks/useFlowState'
import { useFlowNavigation } from './flow-setup/hooks/useFlowNavigation'
import { useTemplateResolver } from './flow-setup/hooks/useTemplateResolver'
import { useDeviceManager } from './flow-setup/hooks/useDeviceManager'

// Import step components for instance (needs special handling)
import { InstanceStep } from './flow-setup/steps/InstanceStep'

// Props
interface FlowSetupFormProps {
  integration: { name: string; display_name?: string }
  mode?: 'create' | 'edit'
  existingInstanceId?: string
  initialDevices?: any[]
  initialConfig?: any
  onCancel: () => void
  onSuccess: () => void
}

// Initialize registries once
let registriesInitialized = false
if (!registriesInitialized) {
  registerStandardFields()
  registerStandardSteps()
  registriesInitialized = true
}

export default function FlowSetupForm({
  integration,
  mode = 'create',
  existingInstanceId,
  initialDevices = [],
  initialConfig = {},
  onCancel,
  onSuccess
}: FlowSetupFormProps) {
  // Schema loading
  const [schema, setSchema] = useState<FlowSetupSchema | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const abortControllerRef = useRef<AbortController | null>(null)
  const isChangingFlow = useRef(false)

  // Load schema
  useEffect(() => {
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const token = getAuthToken()
        const response = await fetch(`/api/integrations/${integration.name}/meta`, {
          headers: { Authorization: `Bearer ${token}` }
        })
        if (!response.ok) throw new Error(`Failed to load setup: ${response.status}`)
        const data = (await response.json()) as FlowSetupSchema
        if (!data.flows || data.flows.length === 0) {
          throw new Error('Integration does not expose any setup flows')
        }
        setSchema(data)
      } catch (e: any) {
        setError(e?.message ?? 'Failed to load setup metadata')
      } finally {
        setLoading(false)
      }
    }

    load()
  }, [integration.name])

  // Flow state management
  const { flowState, flowStateRef, updateFlowState, context, resetFlowState, updateFormValue } =
    useFlowState(integration, undefined)

  // Navigation
  const {
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
  } = useFlowNavigation(schema, flowState, context, v => v)

  // Template resolver
  const { resolveTemplate, resolveDeep } = useTemplateResolver(context)

  // Device manager
  const { collectedDevices, setCollectedDevices, isManuallyAddingDevice, addCurrentDevice, removeDevice, editDevice, clearLoopForms } =
    useDeviceManager(flowState, updateFlowState, initialDevices)

  // Jump to instance step in edit mode
  useEffect(() => {
    if (
      mode === 'edit' &&
      schema &&
      visibleSteps.length > 0 &&
      initialDevices.length > 0 &&
      currentStepIndex === 0 &&
      !isManuallyAddingDevice.current
    ) {
      const instanceStepIndex = visibleSteps.findIndex(step => step.type === 'instance')
      if (instanceStepIndex !== -1) {
        setCurrentStepIndex(instanceStepIndex)
      }
    }
  }, [mode, schema, visibleSteps, initialDevices, currentStepIndex])

  // Handle next step
  const handleNext = useCallback(async () => {
    if (!currentStep) return
    if (isChangingFlow.current) return

    // Validate form step
    if (currentStep.type === 'form') {
      const formValues = flowState.form[currentStep.id] ?? {}
      const missing =
        currentStep.schema?.fields?.filter(field => field.required && !formValues[field.name]) ?? []
      if (missing.length) {
        setError(`Field "${missing[0].label ?? missing[0].name}" is required`)
        return
      }
    }

    // Check tool step result
    if (currentStep.type === 'tool') {
      const key = currentStep.output_key ?? currentStep.tool ?? currentStep.id
      if (!flowState.tools[key]) {
        // Tool will auto-execute in ToolStep component
        return
      }
    }

    // Check OAuth
    if (currentStep.type === 'oauth') {
      const provider = currentStep.oauth?.provider
      if (!provider) {
        setError('OAuth step missing provider')
        return
      }
      if (!flowState.oauth[provider]) {
        setError('Complete OAuth authorization before continuing')
        return
      }
    }

    // Instance step is handled by InstanceStep component itself
    if (currentStep.type === 'instance') {
      // This button shouldn't appear for instance steps
      return
    }

    setError(null)
    advanceStep(1)
  }, [currentStep, flowState, advanceStep])

  // Handle flow actions
  const handleAction = useCallback(
    (action: FlowAction, step?: FlowStep) => {
      switch (action.type) {
        case 'goto_flow': {
          const target = action.flow
          if (!target) return

          isChangingFlow.current = true

          if (abortControllerRef.current) {
            abortControllerRef.current.abort()
            abortControllerRef.current = null
          }

          setBusy(false)
          goToFlow(target)
          setError(null)
          resetFlowState()

          setTimeout(() => {
            isChangingFlow.current = false
          }, 100)
          return
        }
        case 'open_url': {
          if (action.url) window.open(action.url, '_blank', 'noopener')
          return
        }
        case 'reset_flow': {
          resetFlowState()
          setCurrentStepIndex(0)
          autoRanSteps.current = new Set()
          return
        }
        default:
          console.warn('Unhandled flow action', action)
      }
    },
    [goToFlow, resetFlowState, setCurrentStepIndex, autoRanSteps]
  )

  // Handle add another device
  const handleAddAnotherDevice = useCallback(() => {
    if (!schema?.multi_device?.enabled) return

    isManuallyAddingDevice.current = true

    // Add current device
    addCurrentDevice()

    // Clear loop forms
    const loopSteps = getLoopSteps(schema, currentFlow)
    clearLoopForms(loopSteps)

    // Navigate to loop start
    const targetStepIndex = visibleSteps.findIndex(s => s.id === schema.multi_device!.loop_from_step)
    if (targetStepIndex !== -1) {
      setCurrentStepIndex(targetStepIndex)
      setError(null)
    }
  }, [schema, currentFlow, visibleSteps, addCurrentDevice, clearLoopForms, setCurrentStepIndex])

  // Render flow selector
  const renderFlowSelector = () => {
    if (!schema || schema.flows.length <= 1) return null

    return (
      <div className="flex flex-wrap gap-2">
        {schema.flows.map(flow => {
          const selected = flow.id === currentFlowId
          return (
            <Button
              key={flow.id}
              variant={selected ? 'default' : 'outline'}
              onClick={() => goToFlow(flow.id)}
            >
              {flow.name}
            </Button>
          )
        })}
      </div>
    )
  }

  // Render current step
  const renderStep = () => {
    if (!currentStep) return null

    // Special handling for instance step
    if (currentStep.type === 'instance') {
      return (
        <InstanceStep
          step={currentStep}
          flowState={flowState}
          updateFlowState={updateFlowState}
          onNext={handleNext}
          busy={busy}
          error={error}
          setError={setError}
          setBusy={setBusy}
          connectorName={integration.name}
          mode={mode}
          existingInstanceId={existingInstanceId}
          initialConfig={initialConfig}
          context={context}
          schema={schema}
          collectedDevices={collectedDevices}
          onAddDevice={handleAddAnotherDevice}
          onEditDevice={editDevice}
          onRemoveDevice={removeDevice}
          onSuccess={onSuccess}
        />
      )
    }

    // Get step component from registry
    const stepDef = stepRegistry.getStep(currentStep.type)
    if (!stepDef) {
      return (
        <Alert variant="destructive">
          <AlertDescription>Unsupported step type: {currentStep.type}</AlertDescription>
        </Alert>
      )
    }

    const StepComponent = stepDef.component

    return (
      <StepComponent
        step={currentStep}
        flowState={flowState}
        updateFlowState={updateFlowState}
        onNext={handleNext}
        busy={busy}
        error={error}
        setError={setError}
        setBusy={setBusy}
        connectorName={integration.name}
        mode={mode}
        existingInstanceId={existingInstanceId}
        initialConfig={initialConfig}
        context={context}
      />
    )
  }

  // Loading state
  if (loading) {
    return (
      <div className="flex items-center justify-center h-40 text-muted-foreground">
        <Loader2 className="w-6 h-6 animate-spin mr-2" />
        Loading setup…
      </div>
    )
  }

  // Error state
  if (error && !schema) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    )
  }

  // No flow available
  if (!schema || !currentFlow || visibleSteps.length === 0) {
    return (
      <Alert>
        <AlertDescription>Setup flow is not available for this integration.</AlertDescription>
      </Alert>
    )
  }

  const footerActions = currentStep?.actions ?? []
  const isInstanceStep = currentStep?.type === 'instance'

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="space-y-2">
          <h3 className="text-lg font-semibold">{currentFlow.name}</h3>
          {currentFlow.description && (
            <p className="text-sm text-muted-foreground">{currentFlow.description}</p>
          )}
        </div>
        {renderFlowSelector()}
      </div>

      {renderStep()}

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="flex justify-between items-center">
        <div className="flex gap-2 items-center">
          <Button variant="outline" onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
          {footerActions.map(action => (
            <Button
              key={`${currentStep?.id ?? 'flow'}-${action.type}`}
              variant="ghost"
              onClick={() => handleAction(action, currentStep!)}
              className="flex items-center gap-1"
            >
              {action.label ?? action.type}
              {action.type === 'open_url' && <ExternalLink className="h-3 w-3" />}
            </Button>
          ))}
        </div>
        <div className="flex gap-2">
          {currentStepIndex > 0 && (
            <Button variant="ghost" disabled={busy} onClick={() => advanceStep(-1)}>
              Back
            </Button>
          )}
          {!isInstanceStep && (
            <Button disabled={busy} onClick={handleNext}>
              {busy && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Next
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

// Helper function
function getLoopSteps(schema: FlowSetupSchema | null, currentFlow: any): string[] {
  if (!schema?.multi_device?.enabled || !currentFlow) return []

  const fromIndex = currentFlow.steps.findIndex((s: any) => s.id === schema.multi_device!.loop_from_step)
  const toIndex = currentFlow.steps.findIndex((s: any) => s.id === schema.multi_device!.loop_to_step)

  if (fromIndex === -1 || toIndex === -1) return []

  return currentFlow.steps.slice(fromIndex, toIndex + 1).map((s: any) => s.id)
}
