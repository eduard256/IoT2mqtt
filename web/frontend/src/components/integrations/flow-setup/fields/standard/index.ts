import { fieldRegistry } from '../registry'
import { TextField } from './TextField'
import { NumberField } from './NumberField'
import { PasswordField } from './PasswordField'
import { SelectField } from './SelectField'
import { CheckboxField } from './CheckboxField'
import { TextareaField } from './TextareaField'

// Register all standard fields
export function registerStandardFields() {
  fieldRegistry.registerStandard({
    type: 'text',
    component: TextField,
    displayName: 'Text Input',
    description: 'Single-line text input'
  })

  fieldRegistry.registerStandard({
    type: 'number',
    component: NumberField,
    displayName: 'Number Input',
    description: 'Numeric input with validation'
  })

  fieldRegistry.registerStandard({
    type: 'password',
    component: PasswordField,
    displayName: 'Password Input',
    description: 'Masked text input for passwords'
  })

  fieldRegistry.registerStandard({
    type: 'select',
    component: SelectField,
    displayName: 'Select Dropdown',
    description: 'Dropdown selection from options'
  })

  fieldRegistry.registerStandard({
    type: 'checkbox',
    component: CheckboxField,
    displayName: 'Checkbox',
    description: 'Boolean checkbox input'
  })

  fieldRegistry.registerStandard({
    type: 'textarea',
    component: TextareaField,
    displayName: 'Text Area',
    description: 'Multi-line text input'
  })

  // Aliases for common types
  fieldRegistry.registerStandard({
    type: 'ip',
    component: TextField,
    displayName: 'IP Address',
    description: 'IP address input'
  })

  fieldRegistry.registerStandard({
    type: 'url',
    component: TextField,
    displayName: 'URL',
    description: 'URL input'
  })

  fieldRegistry.registerStandard({
    type: 'email',
    component: TextField,
    displayName: 'Email',
    description: 'Email address input'
  })
}
