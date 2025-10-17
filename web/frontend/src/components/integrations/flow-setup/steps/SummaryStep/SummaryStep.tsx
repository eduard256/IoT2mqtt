import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import type { StepComponentProps } from '../../types'

export function SummaryStep({ step, context }: StepComponentProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{step.title ?? 'Summary'}</CardTitle>
        {step.description && <CardDescription>{step.description}</CardDescription>}
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        {(step.sections ?? []).map((section, index) => {
          const resolvedValue = resolveTemplate(section.value, context)

          return (
            <div key={`${step.id}-section-${index}`} className="flex justify-between">
              <span className="text-muted-foreground">{section.label}</span>
              <span>{resolvedValue}</span>
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}

// Helper function
function resolveTemplate(value: any, context: any): any {
  if (typeof value !== 'string') return value

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
