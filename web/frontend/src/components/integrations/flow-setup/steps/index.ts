import { stepRegistry } from './registry'
import { FormStep } from './FormStep'
import { ToolStep } from './ToolStep'
import { SelectStep } from './SelectStep'
import { InstanceStep } from './InstanceStep'
import { OAuthStep } from './OAuthStep'
import { MessageStep } from './MessageStep'
import { SummaryStep } from './SummaryStep'

// Register all standard step types
export function registerStandardSteps() {
  stepRegistry.register({
    type: 'form',
    component: FormStep as any,
    displayName: 'Form Step',
    description: 'Collect user input through form fields'
  })

  stepRegistry.register({
    type: 'tool',
    component: ToolStep as any,
    displayName: 'Tool Step',
    description: 'Execute backend tools and API calls'
  })

  stepRegistry.register({
    type: 'select',
    component: SelectStep as any,
    displayName: 'Select Step',
    description: 'Select items from a list'
  })

  stepRegistry.register({
    type: 'instance',
    component: InstanceStep as any,
    displayName: 'Instance Step',
    description: 'Create or update connector instance'
  })

  stepRegistry.register({
    type: 'oauth',
    component: OAuthStep as any,
    displayName: 'OAuth Step',
    description: 'OAuth authorization flow'
  })

  stepRegistry.register({
    type: 'message',
    component: MessageStep as any,
    displayName: 'Message Step',
    description: 'Display informational message'
  })

  stepRegistry.register({
    type: 'summary',
    component: SummaryStep as any,
    displayName: 'Summary Step',
    description: 'Display summary of collected data'
  })

  // Alias for discovery (same as message)
  stepRegistry.register({
    type: 'discovery',
    component: MessageStep as any,
    displayName: 'Discovery Step',
    description: 'Device discovery step'
  })
}

export { stepRegistry }
