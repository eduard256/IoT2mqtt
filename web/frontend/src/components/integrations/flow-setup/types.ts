import type { ReactNode } from 'react'
import type { FlowStep, FormField } from '@/types/integration'

// Flow State
export interface FlowState {
  form: Record<string, Record<string, any>>
  tools: Record<string, any>
  selection: Record<string, any>
  shared: Record<string, any>
  oauth: Record<string, any>
}

// Field Component Props
export interface FieldComponentProps<T = any> {
  field: FormField
  value: T
  onChange: (value: T) => void
  disabled?: boolean
  error?: string
  connectorName: string
}

// Field Definition for Registry
export interface FieldDefinition {
  type: string
  component: React.ComponentType<FieldComponentProps>
  connectors?: string[]
  displayName: string
  description?: string
  validate?: (value: any, field: FormField) => string | null
}

// Step Component Props
export interface StepComponentProps {
  step: FlowStep
  flowState: FlowState
  updateFlowState: (updater: (prev: FlowState) => FlowState) => void
  onNext: () => void | Promise<void>
  busy: boolean
  error: string | null
  setError: (error: string | null) => void
  setBusy: (busy: boolean) => void
  connectorName: string
  mode: 'create' | 'edit'
  existingInstanceId?: string
  initialConfig?: any
  context: any
}

// Step Definition for Registry
export interface StepDefinition {
  type: string
  component: React.ComponentType<StepComponentProps>
  displayName: string
  description?: string
}

// Context for template resolution
export interface FlowContext {
  integration: { name: string; display_name?: string }
  form: Record<string, any>
  tools: Record<string, any>
  selection: Record<string, any>
  shared: Record<string, any>
  oauth: Record<string, any>
}
