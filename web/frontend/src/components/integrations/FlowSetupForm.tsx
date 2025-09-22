import { useCallback, useEffect, useMemo, useRef, useState, type ChangeEvent } from 'react'
import { Loader2, ExternalLink, Play } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Textarea } from '@/components/ui/textarea'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'

import { getAuthToken } from '@/utils/auth'
import type {
  FlowSetupSchema,
  FlowDefinition,
  FlowStep,
  FlowAction,
  FormField,
  FlowStepType
} from '@/types/integration'
import { cn } from '@/lib/utils'

interface FlowSetupFormProps {
  integration: { name: string; display_name?: string }
  onCancel: () => void
  onSuccess: () => void
}

type FlowState = {
  form: Record<string, Record<string, any>>
  tools: Record<string, any>
  selection: Record<string, any>
  shared: Record<string, any>
  oauth: Record<string, any>
}

const initialFlowState: FlowState = {
  form: {},
  tools: {},
  selection: {},
  shared: {},
  oauth: {}
}

export default function FlowSetupForm({ integration, onCancel, onSuccess }: FlowSetupFormProps) {
  const [schema, setSchema] = useState<FlowSetupSchema | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [flowState, setFlowState] = useState<FlowState>(initialFlowState)
  const [currentFlowId, setCurrentFlowId] = useState<string | null>(null)
  const [currentStepIndex, setCurrentStepIndex] = useState(0)
  const [busy, setBusy] = useState(false)
  const [oauthSession, setOauthSession] = useState<{ id: string; provider: string } | null>(null)
  const autoRanSteps = useRef<Set<string>>(new Set())

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
        const defaultFlow = data.flows.find(flow => flow.default) ?? data.flows[0]
        setCurrentFlowId(defaultFlow.id)
        setCurrentStepIndex(0)
        setFlowState(initialFlowState)
        autoRanSteps.current = new Set()
      } catch (e: any) {
        setError(e?.message ?? 'Failed to load setup metadata')
      } finally {
        setLoading(false)
      }
    }

    load()
  }, [integration.name])

  const context = useMemo(() => ({
    integration,
    form: flowState.form,
    tools: flowState.tools,
    selection: flowState.selection,
    shared: flowState.shared,
    oauth: flowState.oauth
  }), [integration, flowState])

  const currentFlow: FlowDefinition | undefined = useMemo(() => {
    if (!schema || !currentFlowId) return undefined
    return schema.flows.find(flow => flow.id === currentFlowId) ?? schema.flows[0]
  }, [schema, currentFlowId])

  const visibleSteps: FlowStep[] = useMemo(() => {
    if (!currentFlow) return []
    return currentFlow.steps.filter(step => evaluateConditions(step.conditions))
  }, [currentFlow, context])

  useEffect(() => {
    if (currentStepIndex >= visibleSteps.length) {
      setCurrentStepIndex(visibleSteps.length > 0 ? visibleSteps.length - 1 : 0)
    }
  }, [visibleSteps, currentStepIndex])

  const currentStep = visibleSteps[currentStepIndex]

  useEffect(() => {
    if (!currentStep) return
    if (currentStep.type === 'tool' && currentStep.auto_advance && !autoRanSteps.current.has(currentStep.id)) {
      autoRanSteps.current.add(currentStep.id)
      void executeTool(currentStep)
    }
  }, [currentStep])

  useEffect(() => {
    const listener = (event: MessageEvent) => {
      if (!event.data || typeof event.data !== 'object') return
      if (!('status' in event.data)) return
      if (event.data.status === 'authorized' && event.data.session_id) {
        void fetchOAuthSession(event.data.session_id)
      }
    }
    window.addEventListener('message', listener)
    return () => window.removeEventListener('message', listener)
  }, [])

  const fetchOAuthSession = useCallback(async (sessionId: string) => {
    try {
      const token = getAuthToken()
      const response = await fetch(`/api/oauth/session/${sessionId}`, {
        headers: { Authorization: `Bearer ${token}` }
      })
      if (!response.ok) throw new Error('Failed to load OAuth session')
      const session = await response.json()
      setFlowState(prev => ({
        ...prev,
        oauth: {
          ...prev.oauth,
          [session.provider]: session
        }
      }))
      setOauthSession(null)
      if (currentStep?.auto_advance) {
        void handleNext()
      }
    } catch (e: any) {
      setError(e?.message ?? 'Failed to fetch OAuth session')
    }
  }, [currentStep])

  function evaluateConditions(conditions?: Record<string, unknown>): boolean {
    if (!conditions) return true
    return Object.entries(conditions).every(([path, expected]) => {
      const actual = readContextPath(path)
      const expectedValue = typeof expected === 'string' ? resolveTemplate(expected) : expected
      if (Array.isArray(expectedValue)) {
        return Array.isArray(actual) && expectedValue.every(item => actual.includes(item))
      }
      return actual === expectedValue
    })
  }

  function readContextPath(path: string): any {
    const segments = path.split('.').filter(Boolean)
    let cursor: any = context
    for (const segment of segments) {
      if (cursor == null) return undefined
      cursor = cursor[segment as keyof typeof cursor]
    }
    return cursor
  }

  function resolveTemplate(value: unknown, extra: Record<string, unknown> = {}): any {
    if (typeof value !== 'string') return value
    const singleMatch = value.match(/^{{\s*([^}]+)\s*}}$/)
    if (singleMatch) {
      const rawPath = singleMatch[1]
      const combined = { ...context, ...extra }
      const segments = rawPath.split('.').filter(Boolean)
      let pointer: any = combined
      for (const segment of segments) {
        if (pointer == null) return ''
        pointer = pointer[segment]
      }
      return pointer ?? ''
    }

    const matcher = /{{\s*([^}]+)\s*}}/g
    return value.replace(matcher, (_, rawPath) => {
      const path = rawPath.trim()
      const combined = { ...context, ...extra }
      const segments = path.split('.').filter(Boolean)
      let pointer: any = combined
      for (const segment of segments) {
        if (pointer == null) return ''
        pointer = pointer[segment]
      }
      if (pointer == null) return ''
      if (typeof pointer === 'object') return JSON.stringify(pointer)
      return String(pointer)
    })
  }

  function resolveDeep<T = any>(payload: T, extra: Record<string, unknown> = {}): T {
    if (payload == null) return payload
    if (typeof payload === 'string') {
      return resolveTemplate(payload, extra) as T
    }
    if (Array.isArray(payload)) {
      return payload.map(item => resolveDeep(item, extra)) as T
    }
    if (typeof payload === 'object') {
      const result: Record<string, any> = {}
      for (const [key, val] of Object.entries(payload)) {
        result[key] = resolveDeep(val, extra)
      }
      return result as T
    }
    return payload
  }

  function updateFormValue(stepId: string, field: FormField, value: any) {
    setFlowState(prev => ({
      ...prev,
      form: {
        ...prev.form,
        [stepId]: {
          ...(prev.form[stepId] ?? {}),
          [field.name]: value
        }
      }
    }))
  }

  async function executeTool(step: FlowStep) {
    if (!schema) return
    if (!step.tool) {
      setError('Tool step missing tool name')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const token = getAuthToken()
      const inputPayload = resolveDeep(step.input ?? {})
      const response = await fetch(`/api/integrations/${integration.name}/tools/execute`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ tool: step.tool, input: inputPayload })
      })
      const data = await response.json().catch(() => ({}))
      if (!response.ok || data.ok === false) {
        throw new Error(data?.error?.message ?? data?.detail ?? 'Tool execution failed')
      }
      const storageKey = step.output_key ?? step.tool
      setFlowState(prev => ({
        ...prev,
        tools: {
          ...prev.tools,
          [storageKey]: data
        }
      }))
      if (step.auto_advance) {
        setBusy(false)
        await handleNext()
        return
      }
    } catch (e: any) {
      setError(e?.message ?? 'Tool execution failed')
    }
    setBusy(false)
  }

  async function handleNext() {
    if (!currentStep) return

    if (currentStep.type === 'form') {
      const formValues = flowState.form[currentStep.id] ?? {}
      const missing = currentStep.schema?.fields?.filter(field => field.required && !formValues[field.name]) ?? []
      if (missing.length) {
        setError(`Field "${missing[0].label ?? missing[0].name}" is required`)
        return
      }
    }

    if (currentStep.type === 'tool') {
      const key = currentStep.output_key ?? currentStep.tool ?? currentStep.id
      if (!flowState.tools[key]) {
        await executeTool(currentStep)
        return
      }
    }

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

    if (currentStep.type === 'instance') {
      await createInstance(currentStep)
      return
    }

    advanceStep(1)
  }

  function advanceStep(delta: number) {
    setError(null)
    setCurrentStepIndex(index => {
      const next = index + delta
      if (next < 0) return 0
      if (next >= visibleSteps.length) {
        onSuccess()
        return index
      }
      return next
    })
  }

  async function createInstance(step: FlowStep) {
    if (!step.instance) {
      setError('Instance step missing configuration')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const resolved = resolveDeep(step.instance)
      const payload = {
        instance_id: resolved.instance_id,
        connector_type: resolved.connector_type ?? integration.name,
        friendly_name: resolved.friendly_name ?? resolved.instance_id,
        config: resolved.config ?? {},
        devices: resolved.devices ?? [],
        enabled: resolved.enabled ?? true,
        update_interval: resolved.update_interval ?? 15,
        secrets: resolved.secrets ?? undefined
      }
      if (!payload.instance_id) {
        throw new Error('Instance id is required to create connector instance')
      }
      if (typeof payload.update_interval === 'string') {
        const trimmed = payload.update_interval.trim()
        const numeric = Number(trimmed)
        payload.update_interval = trimmed && Number.isFinite(numeric) ? numeric : 15
      }
      if (payload.config && typeof payload.config.duration === 'string') {
        const trimmed = payload.config.duration.trim()
        const numericDuration = Number(trimmed)
        payload.config.duration = trimmed && Number.isFinite(numericDuration) ? numericDuration : 300
      }
      if (payload.config && typeof payload.config.discovery_interval === 'string') {
        const trimmed = payload.config.discovery_interval.trim()
        const numericInterval = Number(trimmed)
        if (trimmed && Number.isFinite(numericInterval)) payload.config.discovery_interval = numericInterval
      }
      if (payload.devices && Array.isArray(payload.devices)) {
        payload.devices = payload.devices.map(device => {
          const mapped = { ...device }
          if (typeof mapped.port === 'string') {
            const trimmed = mapped.port.trim()
            const numericPort = Number(trimmed)
            mapped.port = trimmed && Number.isFinite(numericPort) ? numericPort : 55443
          }
          return mapped
        })
      }
      const token = getAuthToken()
      const response = await fetch('/api/instances', {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify(payload)
      })
      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(data?.detail ?? 'Failed to create instance')
      }
      onSuccess()
    } catch (e: any) {
      setError(e?.message ?? 'Failed to create instance')
    } finally {
      setBusy(false)
    }
  }

  function handleAction(action: FlowAction, step?: FlowStep) {
    switch (action.type) {
      case 'goto_flow': {
        const target = action.flow
        if (!target) return
        setCurrentFlowId(target)
        setCurrentStepIndex(0)
        autoRanSteps.current = new Set()
        return
      }
      case 'open_url': {
        if (action.url) window.open(action.url, '_blank', 'noopener')
        return
      }
      case 'reset_flow': {
        setFlowState(initialFlowState)
        setCurrentStepIndex(0)
        autoRanSteps.current = new Set()
        return
      }
      case 'rerun_step': {
        if (step && step.type === 'tool') {
          autoRanSteps.current.delete(step.id)
          void executeTool(step)
        }
        return
      }
      default:
        console.warn('Unhandled flow action', action)
    }
  }

  async function startOAuth(step: FlowStep) {
    const provider = step.oauth?.provider
    if (!provider) {
      setError('OAuth provider not specified')
      return
    }
    setBusy(true)
    setError(null)
    try {
      const token = getAuthToken()
      const response = await fetch(`/api/oauth/${provider}/session`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ redirect_uri: step.oauth?.redirect_uri })
      })
      if (!response.ok) {
        const data = await response.json().catch(() => ({}))
        throw new Error(data?.detail ?? 'Failed to start OAuth flow')
      }
      const data = await response.json()
      setOauthSession({ id: data.session_id, provider })
      const popup = window.open(data.authorization_url, '_blank', 'width=600,height=700')
      if (!popup) {
        throw new Error('Please allow popups to continue OAuth authorization')
      }
    } catch (e: any) {
      setError(e?.message ?? 'Failed to start OAuth flow')
    } finally {
      setBusy(false)
    }
  }

  function renderField(step: FlowStep, field: FormField) {
    const values = flowState.form[step.id] ?? {}
    const value = values[field.name] ?? (field.default ?? '')
    if (!evaluateConditions(field.conditions)) return null

    if (field.type === 'select') {
      return (
        <div key={field.name} className="space-y-2">
          <Label>{field.label ?? field.name}</Label>
          <Select
            value={value}
            onValueChange={val => updateFormValue(step.id, field, val)}
          >
            <SelectTrigger>
              <SelectValue placeholder={field.placeholder ?? 'Select option'} />
            </SelectTrigger>
            <SelectContent>
              {(field.options ?? []).map(option => (
                <SelectItem key={option.value} value={option.value}>{option.label}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      )
    }

    if (field.type === 'checkbox') {
      return (
        <div key={field.name} className="flex items-center space-x-2">
          <Input
            type="checkbox"
            checked={Boolean(value)}
            onChange={event => updateFormValue(step.id, field, event.target.checked)}
          />
          <Label className="font-normal">{field.label ?? field.name}</Label>
        </div>
      )
    }

    const inputType = field.type === 'textarea' ? 'text' : field.type === 'password' ? 'password' : 'text'
    const inputProps = {
      placeholder: field.placeholder,
      value: value ?? '',
      onChange: (event: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
        updateFormValue(step.id, field, event.target.value)
    }

    return (
      <div key={field.name} className="space-y-2">
        <Label>{field.label ?? field.name}</Label>
        {field.type === 'textarea' ? (
          <Textarea {...inputProps} rows={field.multiline ? 6 : 3} />
        ) : (
          <Input type={inputType} {...inputProps} />
        )}
      </div>
    )
  }

  function renderForm(step: FlowStep) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{step.title ?? 'Configuration'}</CardTitle>
          {step.description && <CardDescription>{step.description}</CardDescription>}
        </CardHeader>
        <CardContent className="space-y-4">
          {step.schema?.fields?.map(field => renderField(step, field))}
        </CardContent>
      </Card>
    )
  }

  function renderTool(step: FlowStep) {
    const storageKey = step.output_key ?? step.tool ?? step.id
    const result = flowState.tools[storageKey]
    return (
      <Card>
        <CardHeader>
          <CardTitle>{step.title ?? 'Run Tool'}</CardTitle>
          {step.description && <CardDescription>{step.description}</CardDescription>}
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
            {busy ? 'Executing tool…' : result ? 'Tool executed successfully' : 'Execute the tool to continue'}
          </div>
          <Button variant="secondary" disabled={busy} onClick={() => executeTool(step)}>
            {busy && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}Run tool
          </Button>
          {result && (
            <pre className="bg-muted text-xs p-3 rounded overflow-x-auto">
              {JSON.stringify(result, null, 2)}
            </pre>
          )}
        </CardContent>
      </Card>
    )
  }

  function renderSelect(step: FlowStep) {
    const rawItems = resolveDeep(step.items ?? '')
    const items = Array.isArray(rawItems) ? rawItems : []
    const storageKey = step.output_key ?? step.id
    const currentSelection = flowState.selection[storageKey] ?? (step.multi_select ? [] : null)

    const toggle = (value: any) => {
      setFlowState(prev => {
        const selection = prev.selection[storageKey]
        if (step.multi_select) {
          const list = Array.isArray(selection) ? [...selection] : []
          const index = list.findIndex(item => JSON.stringify(item) === JSON.stringify(value))
          if (index >= 0) list.splice(index, 1)
          else list.push(value)
          return {
            ...prev,
            selection: { ...prev.selection, [storageKey]: list }
          }
        }
        return {
          ...prev,
          selection: { ...prev.selection, [storageKey]: value }
        }
      })
    }

    return (
      <Card>
        <CardHeader>
          <CardTitle>{step.title ?? 'Select items'}</CardTitle>
          {step.description && <CardDescription>{step.description}</CardDescription>}
        </CardHeader>
        <CardContent className="space-y-3">
          {items.length === 0 && (
            <Alert>
              <AlertDescription>No options available. Run the previous step again if data was expected.</AlertDescription>
            </Alert>
          )}
          {items.map((item, index) => {
            const itemValue = resolveDeep(step.item_value ?? '{{ item }}', { item })
            const itemLabel = resolveTemplate(step.item_label ?? '{{ item }}', { item })
            const isActive = step.multi_select
              ? Array.isArray(currentSelection) && currentSelection.some((sel: any) => JSON.stringify(sel) === JSON.stringify(itemValue))
              : JSON.stringify(currentSelection) === JSON.stringify(itemValue)
            return (
              <button
                type="button"
                key={`${storageKey}-${index}`}
                className={cn(
                  'w-full text-left border rounded p-3 transition-colors',
                  isActive ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50'
                )}
                onClick={() => toggle(itemValue)}
              >
                {itemLabel}
              </button>
            )
          })}
        </CardContent>
      </Card>
    )
  }

  function renderSummary(step: FlowStep) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{step.title ?? 'Summary'}</CardTitle>
          {step.description && <CardDescription>{step.description}</CardDescription>}
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {(step.sections ?? []).map((section, index) => (
            <div key={`${step.id}-section-${index}`} className="flex justify-between">
              <span className="text-muted-foreground">{section.label}</span>
              <span>{resolveTemplate(section.value)}</span>
            </div>
          ))}
        </CardContent>
      </Card>
    )
  }

  function renderMessage(step: FlowStep) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{step.title ?? 'Information'}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">{step.description ?? 'Follow the instructions to continue.'}</p>
        </CardContent>
      </Card>
    )
  }

  function renderInstance(step: FlowStep) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>{step.title ?? 'Create Instance'}</CardTitle>
          {step.description && <CardDescription>{step.description}</CardDescription>}
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">
            Review the configuration and press Finish to create the connector instance.
          </p>
        </CardContent>
      </Card>
    )
  }

  function renderOAuth(step: FlowStep) {
    const provider = step.oauth?.provider ?? 'provider'
    const sessionActive = flowState.oauth[provider]
    return (
      <Card>
        <CardHeader>
          <CardTitle>{step.title ?? `Authorize ${provider}`}</CardTitle>
          {step.description && <CardDescription>{step.description}</CardDescription>}
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Sign in with your {provider} account to continue. A popup window will open to complete the authorization.
          </p>
          <Button disabled={busy} onClick={() => startOAuth(step)}>
            {busy && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}Authorize {provider}
          </Button>
          {sessionActive && (
            <Alert>
              <AlertDescription>
                Connected as {sessionActive.tokens?.account ?? 'authorized account'}
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>
    )
  }

  function renderStep(step: FlowStep) {
    switch (step.type as FlowStepType) {
      case 'form':
        return renderForm(step)
      case 'tool':
        return renderTool(step)
      case 'select':
        return renderSelect(step)
      case 'summary':
        return renderSummary(step)
      case 'message':
        return renderMessage(step)
      case 'instance':
        return renderInstance(step)
      case 'oauth':
        return renderOAuth(step)
      case 'discovery':
        return renderMessage(step)
      default:
        return (
          <Alert>
            <AlertDescription>Unsupported step type: {step.type}</AlertDescription>
          </Alert>
        )
    }
  }

  function renderFlowSelector() {
    if (!schema || schema.flows.length <= 1) return null
    return (
      <div className="flex flex-wrap gap-2">
        {schema.flows.map(flow => {
          const selected = flow.id === currentFlowId
          return (
            <Button
              key={flow.id}
              variant={selected ? 'default' : 'outline'}
              onClick={() => {
                setCurrentFlowId(flow.id)
                setCurrentStepIndex(0)
                autoRanSteps.current = new Set()
              }}
            >
              {flow.name}
            </Button>
          )
        })}
      </div>
    )
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-40 text-muted-foreground">
        <Loader2 className="w-6 h-6 animate-spin mr-2" />Loading setup…
      </div>
    )
  }

  if (error) {
    return (
      <Alert>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    )
  }

  if (!schema || !currentFlow || visibleSteps.length === 0) {
    return (
      <Alert>
        <AlertDescription>Setup flow is not available for this integration.</AlertDescription>
      </Alert>
    )
  }

  const footerActions = currentStep?.actions ?? []

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

      {currentStep && renderStep(currentStep)}

      {error && (
        <Alert>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="flex justify-between items-center">
        <div className="flex gap-2 items-center">
          <Button variant="outline" onClick={onCancel} disabled={busy}>Cancel</Button>
          {footerActions.map(action => (
            <Button
              key={`${currentStep?.id ?? 'flow'}-${action.type}`}
              variant="ghost"
              onClick={() => handleAction(action, currentStep)}
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
          {currentStep.type === 'instance' ? (
            <Button disabled={busy} onClick={() => createInstance(currentStep)}>
              {busy && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}Finish
            </Button>
          ) : (
            <Button disabled={busy} onClick={handleNext}>
              {busy && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}Next
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
