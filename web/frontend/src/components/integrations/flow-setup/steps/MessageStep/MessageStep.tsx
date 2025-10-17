import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { StepComponentProps } from '../../types'

export function MessageStep({ step }: StepComponentProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{step.title ?? 'Information'}</CardTitle>
      </CardHeader>
      <CardContent>
        <p className="text-sm text-muted-foreground">
          {step.description ?? 'Follow the instructions to continue.'}
        </p>
      </CardContent>
    </Card>
  )
}
