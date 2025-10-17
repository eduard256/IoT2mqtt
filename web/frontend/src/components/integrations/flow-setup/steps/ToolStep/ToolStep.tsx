import { useEffect, useRef } from 'react'
import { Loader2, Play } from 'lucide-react'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { getAuthToken } from '@/utils/auth'
import type { StepComponentProps } from '../../types'

export function ToolStep({
  step,
  flowState,
  updateFlowState,
  busy,
  setBusy,
  setError,
  context,
  connectorName,
  onNext
}: StepComponentProps) {
  const abortControllerRef = useRef<AbortController | null>(null)
  const hasExecutedRef = useRef(false)

  const executeTool = async () => {
    if (!step.tool) {
      setError('Tool step missing tool name')
      return
    }

    if (hasExecutedRef.current) {
      return
    }
    hasExecutedRef.current = true

    setBusy(true)
    setError(null)

    // Create new AbortController for this request
    abortControllerRef.current = new AbortController()

    try {
      const token = getAuthToken()

      // Resolve input payload with current context
      const inputPayload = resolveDeepPayload(step.input ?? {}, context)

      // Validate required fields for specific tools
      if (step.tool === 'validate_device' || step.tool === 'validate_connection') {
        if (!inputPayload.host && !inputPayload.ip) {
          throw new Error('Host/IP address is required for validation')
        }
      }

      const response = await fetch(`/api/integrations/${connectorName}/tools/execute`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ tool: step.tool, input: inputPayload }),
        signal: abortControllerRef.current.signal
      })

      const data = await response.json().catch(() => ({}))
      if (!response.ok || data.ok === false) {
        throw new Error(data?.error?.message ?? data?.detail ?? 'Tool execution failed')
      }

      // Store result in flowState
      const storageKey = step.output_key ?? step.tool
      updateFlowState(prev => ({
        ...prev,
        tools: {
          ...prev.tools,
          [storageKey]: data
        }
      }))

      // Auto-advance if configured
      if (step.auto_advance) {
        setBusy(false)
        await onNext()
        return
      }
    } catch (e: any) {
      // Don't show error if request was aborted
      if (e.name === 'AbortError') {
        setBusy(false)
        return
      }
      console.error('[executeTool] Error:', e)
      setError(e?.message ?? 'Tool execution failed')
      hasExecutedRef.current = false
    }
    setBusy(false)
  }

  // Auto-execute on mount if auto_advance is enabled
  useEffect(() => {
    const storageKey = step.output_key ?? step.tool ?? step.id
    const hasResult = flowState.tools[storageKey]

    if (step.auto_advance && !hasResult && !hasExecutedRef.current) {
      void executeTool()
    }

    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort()
      }
    }
  }, [])

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
          {busy ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Play className="h-4 w-4" />
          )}
          {busy
            ? 'Executing tool…'
            : result
            ? 'Tool executed successfully'
            : 'Execute the tool to continue'}
        </div>

        {!step.auto_advance && (
          <Button variant="secondary" disabled={busy} onClick={executeTool}>
            {busy && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
            Run tool
          </Button>
        )}

        {result && (
          <pre className="bg-muted text-xs p-3 rounded overflow-x-auto max-h-96">
            {JSON.stringify(result, null, 2)}
          </pre>
        )}
      </CardContent>
    </Card>
  )
}

// Helper function to resolve templates in payload
function resolveDeepPayload(payload: any, context: any): any {
  if (payload == null) return payload

  if (typeof payload === 'string') {
    return resolveTemplate(payload, context)
  }

  if (Array.isArray(payload)) {
    return payload.map(item => resolveDeepPayload(item, context))
  }

  if (typeof payload === 'object') {
    const result: Record<string, any> = {}
    for (const [key, val] of Object.entries(payload)) {
      result[key] = resolveDeepPayload(val, context)
    }
    return result
  }

  return payload
}

function resolveTemplate(value: string, context: any): any {
  const singleMatch = value.match(/^{{\s*([^}]+)\s*}}$/)
  if (singleMatch) {
    const path = singleMatch[1].trim()
    const segments = path.split('.').map(s => s.trim()).filter(s => s)
    let pointer: any = context
    for (const segment of segments) {
      if (pointer == null) return ''
      pointer = pointer[segment]
    }
    return pointer ?? ''
  }

  const matcher = /{{\s*([^}]+)\s*}}/g
  return value.replace(matcher, (_, rawPath) => {
    const path = rawPath.trim()
    const segments = path.split('.').map(s => s.trim()).filter(s => s)
    let pointer: any = context
    for (const segment of segments) {
      if (pointer == null) return ''
      pointer = pointer[segment]
    }
    if (pointer == null) return ''
    if (typeof pointer === 'object') return JSON.stringify(pointer)
    return String(pointer)
  })
}
