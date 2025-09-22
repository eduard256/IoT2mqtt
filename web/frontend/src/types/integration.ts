export type FormFieldType =
  | 'text'
  | 'password'
  | 'number'
  | 'select'
  | 'checkbox'
  | 'ip'
  | 'url'
  | 'email'
  | 'textarea'

export interface FlowAction {
  type: 'goto_flow' | 'open_url' | 'reset_flow' | 'rerun_step' | 'submit' | 'close' | 'custom'
  label?: string
  flow?: string
  url?: string
  payload?: Record<string, unknown>
  confirm?: {
    title?: string
    description?: string
  }
}

export interface FormFieldOption {
  value: string
  label: string
}

export interface FormField {
  type: FormFieldType
  name: string
  label?: string
  description?: string
  required?: boolean
  default?: unknown
  placeholder?: string
  options?: FormFieldOption[]
  pattern?: string
  min?: number
  max?: number
  step?: number
  multiline?: boolean
  secret?: boolean
  conditions?: Record<string, unknown>
}

export interface FormSchema {
  fields: FormField[]
}

export type FlowStepType =
  | 'form'
  | 'tool'
  | 'select'
  | 'summary'
  | 'discovery'
  | 'message'
  | 'instance'
  | 'oauth'

export interface FlowStep {
  id: string
  type: FlowStepType
  title?: string
  description?: string
  schema?: FormSchema
  tool?: string
  input?: Record<string, unknown>
  output_key?: string
  items?: string
  item_label?: string
  item_value?: string
  multi_select?: boolean
  sections?: Array<{ label: string; value: unknown }>
  actions?: FlowAction[]
  auto_advance?: boolean
  optional?: boolean
  conditions?: Record<string, unknown>
  instance?: Record<string, unknown>
  oauth?: {
    provider: string
    scopes?: string[]
    redirect_uri?: string
  }
}

export interface FlowDefinition {
  id: string
  name: string
  description?: string
  default?: boolean
  prerequisites?: string[]
  steps: FlowStep[]
}

export interface ToolDefinition {
  entry: string
  timeout?: number
  network?: 'none' | 'local' | 'internet'
  secrets?: string[]
  environment?: Record<string, string>
}

export interface FlowSetupSchema {
  version: string
  display_name: string
  description?: string
  author?: string
  branding?: Record<string, unknown>
  requirements?: Record<string, unknown>
  flows: FlowDefinition[]
  tools: Record<string, ToolDefinition>
  discovery?: Record<string, unknown>
  secrets?: string[]
}

export interface IntegrationSummary {
  name: string
  display_name: string
  version?: string
  author?: string
  description?: string
  branding?: Record<string, unknown>
  discovery?: Record<string, unknown>
  capabilities?: unknown[]
  default_flow?: string
  flows?: Array<{ id: string; name: string; description?: string }>
}
