import { useEffect, useMemo, useState } from 'react'
import { getAuthToken } from '@/utils/auth'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Alert, AlertDescription } from '@/components/ui/alert'
import { Loader2 } from 'lucide-react'

type AnyObj = Record<string, any>

interface FlowSetupFormProps {
  integration: { name: string; display_name?: string }
  onCancel: () => void
  onSuccess: () => void
}

export default function FlowSetupForm({ integration, onCancel, onSuccess }: FlowSetupFormProps) {
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [setup, setSetup] = useState<AnyObj | null>(null)
  const [current, setCurrent] = useState(0)
  const [busy, setBusy] = useState(false)

  // Flow state storage
  const [flowState, setFlowState] = useState<AnyObj>({ form: {}, tools: {}, selection: {} })

  const steps = useMemo(() => setup?.setup_flows?.[0]?.steps || [], [setup])

  useEffect(() => {
    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const token = getAuthToken()
        const res = await fetch(`/api/integrations/${integration.name}/setup`, {
          headers: { 'Authorization': `Bearer ${token}` }
        })
        if (!res.ok) throw new Error(`Failed to load setup: ${res.status}`)
        const data = await res.json()
        setSetup(data)
      } catch (e: any) {
        setError(e?.message || 'Failed to load setup')
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [integration.name])

  const resolve = (template: any, extra: AnyObj = {}): any => {
    if (template == null) return template
    if (typeof template !== 'string') return template
    // Simple mustache {{ path.to.value }}
    return template.replace(/\{\{\s*([^}]+)\s*\}\}/g, (_m, path) => {
      const parts = path.split('.')
      let ctx: any = { ...flowState, ...extra }
      for (const p of parts) {
        const key = p.trim()
        if (key in ctx) ctx = ctx[key]
        else return ''
      }
      return ctx == null ? '' : String(ctx)
    })
  }

  const next = async () => {
    if (!steps[current]) return
    const step = steps[current]
    try {
      if (step.type === 'form') {
        // Basic required validation
        const values = flowState.form[step.id] || {}
        for (const f of step.schema?.fields || []) {
          if (f.required && (values[f.name] === undefined || values[f.name] === '')) {
            setError(`Field '${f.label || f.name}' is required`)
            return
          }
        }
      }
      if (step.type === 'run_tool') {
        setBusy(true)
        setError(null)
        const token = getAuthToken()
        // Build input by resolving templates
        const input: AnyObj = {}
        for (const [k, v] of Object.entries(step.input || {})) {
          input[k] = resolve(v)
        }
        const res = await fetch(`/api/integrations/${integration.name}/tools/execute`, {
          method: 'POST',
          headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
          body: JSON.stringify({ tool: step.tool, input })
        })
        const data = await res.json().catch(() => ({}))
        if (!res.ok || data.ok === false) {
          const msg = data?.error?.message || data?.detail || 'Tool execution failed'
          setError(msg)
          setBusy(false)
          return
        }
        setFlowState(s => ({ ...s, tools: { ...s.tools, [step.output_key || step.tool]: data } }))
        setBusy(false)
      }
      if (current < steps.length - 1) setCurrent(current + 1)
      else onSuccess()
    } catch (e: any) {
      setError(e?.message || 'Step failed')
      setBusy(false)
    }
  }

  const back = () => {
    if (current > 0) setCurrent(current - 1)
  }

  const handleCreateInstance = async (step: AnyObj) => {
    try {
      setBusy(true)
      setError(null)
      // Resolve top-level fields
      const instance_id = resolve(step.instance_id)
      const friendly_name = resolve(step.friendly_name)
      const connector_type = step.connector_type || integration.name
      const devices = (step.devices || []).map((d: any) => {
        const out: AnyObj = {}
        for (const [k, v] of Object.entries(d)) out[k] = resolve(v)
        return out
      })
      const token = getAuthToken()
      const res = await fetch('/api/instances', {
        method: 'POST',
        headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
        body: JSON.stringify({ instance_id, connector_type, friendly_name, config: {}, devices, enabled: true, update_interval: 15 })
      })
      if (!res.ok) {
        const data = await res.json().catch(() => ({}))
        throw new Error(data?.detail || 'Failed to create instance')
      }
      onSuccess()
    } catch (e: any) {
      setError(e?.message || 'Failed to create instance')
    } finally {
      setBusy(false)
    }
  }

  const renderForm = (step: AnyObj) => {
    const values = flowState.form[step.id] || {}
    const setVal = (name: string, val: any) => setFlowState(s => ({ ...s, form: { ...s.form, [step.id]: { ...(s.form[step.id] || {}), [name]: val } } }))
    return (
      <Card>
        <CardHeader>
          <CardTitle>{step.title || 'Configuration'}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {(step.schema?.fields || []).map((f: any) => {
            if (f.type === 'select') {
              return (
                <div key={f.name} className="space-y-2">
                  <Label>{f.label || f.name}</Label>
                  <Select value={values[f.name] || ''} onValueChange={(v) => setVal(f.name, v)}>
                    <SelectTrigger>
                      <SelectValue placeholder={f.placeholder || 'Select...'} />
                    </SelectTrigger>
                    <SelectContent>
                      {(f.options || []).map((opt: any) => (
                        <SelectItem key={opt.value} value={opt.value}>{opt.label}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              )
            }
            const type = f.type === 'password' ? 'password' : 'text'
            return (
              <div key={f.name} className="space-y-2">
                <Label>{f.label || f.name}</Label>
                <Input type={type} value={values[f.name] || ''} onChange={(e) => setVal(f.name, e.target.value)} placeholder={f.placeholder} />
              </div>
            )
          })}
        </CardContent>
      </Card>
    )
  }

  const renderSelectList = (step: AnyObj) => {
    const itemsPath = step.items
    let items: any[] = []
    // Resolve path like {{ tools.cloud_devices.result.devices }}
    const match = /\{\{\s*([^}]+)\s*\}\}/.exec(itemsPath || '')
    if (match) {
      const parts = match[1].split('.')
      let ctx: any = flowState
      for (const p of parts) {
        const key = p.trim()
        if (key in ctx) ctx = ctx[key]
        else { ctx = []; break }
      }
      items = Array.isArray(ctx) ? ctx : []
    }
    const selected = flowState.selection[step.output_key] || ''
    const choose = (val: string) => setFlowState(s => ({ ...s, selection: { ...s.selection, [step.output_key]: val } }))
    const renderLabel = (item: any) => resolve(step.item_label || '{{ item }}', { item })

    return (
      <Card>
        <CardHeader><CardTitle>{step.title || 'Select'}</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          {items.length === 0 ? (
            <Alert><AlertDescription>No items</AlertDescription></Alert>
          ) : items.map((it: any) => {
            const value = resolve(step.item_value || '{{ item }}', { item: it })
            const label = renderLabel(it)
            const active = selected === value
            return (
              <div key={value} className={`p-3 border rounded cursor-pointer ${active ? 'border-primary' : 'border-muted'}`} onClick={() => choose(value)}>
                {label}
              </div>
            )
          })}
        </CardContent>
      </Card>
    )
  }

  const renderSummary = (step: AnyObj) => (
    <Card>
      <CardHeader><CardTitle>{step.title || 'Summary'}</CardTitle></CardHeader>
      <CardContent className="space-y-2">
        {(step.sections || []).map((s: any, idx: number) => (
          <div key={idx} className="flex justify-between"><span className="text-muted-foreground">{s.label}</span><span>{resolve(s.value)}</span></div>
        ))}
      </CardContent>
    </Card>
  )

  if (loading) {
    return <div className="flex items-center justify-center h-40"><Loader2 className="w-6 h-6 animate-spin" /></div>
  }
  if (error) {
    return (
      <Alert>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    )
  }
  if (!setup || steps.length === 0) {
    return (
      <Alert>
        <AlertDescription>Setup flow not defined.</AlertDescription>
      </Alert>
    )
  }

  const step = steps[current]

  return (
    <div className="space-y-4">
      {step.type === 'form' && renderForm(step)}
      {step.type === 'run_tool' && (
        <Card>
          <CardHeader><CardTitle>Executing {step.tool}...</CardTitle></CardHeader>
          <CardContent>
            {busy ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="w-4 h-4 animate-spin" /> Running tool</div>
            ) : (
              <div className="text-sm text-muted-foreground">Ready to execute</div>
            )}
          </CardContent>
        </Card>
      )}
      {step.type === 'select_list' && renderSelectList(step)}
      {step.type === 'summary' && renderSummary(step)}
      {step.type === 'create_instance' && (
        <Card>
          <CardHeader><CardTitle>Create Instance</CardTitle></CardHeader>
          <CardContent className="text-sm text-muted-foreground">Press Finish to create the instance.</CardContent>
        </Card>
      )}

      <div className="flex justify-between">
        <Button variant="outline" onClick={onCancel}>Cancel</Button>
        <div className="flex gap-2">
          {current > 0 && <Button variant="ghost" onClick={back}>Back</Button>}
          {step.type === 'create_instance' ? (
            <Button disabled={busy} onClick={() => handleCreateInstance(step)}>
              {busy && <Loader2 className="w-4 h-4 mr-2 animate-spin" />} Finish
            </Button>
          ) : (
            <Button disabled={busy} onClick={next}>
              {busy && <Loader2 className="w-4 h-4 mr-2 animate-spin" />} Next
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}

