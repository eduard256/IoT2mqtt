import { useState, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { ChevronRight, ChevronLeft, Loader2, Check } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select'
import { Checkbox } from '@/components/ui/checkbox'
import { toast } from '@/hooks/use-toast'
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog'
import { Progress } from '@/components/ui/progress'
import LogTerminal from './LogTerminal'

interface IntegrationWizardProps {
  integration: any
  mode: 'create' | 'edit'
  onClose: () => void
}

interface SetupField {
  type: string
  name: string
  label: string
  description?: string
  required?: boolean
  default?: any
  placeholder?: string
  validation?: any
  options?: any[]
  min?: number
  max?: number
  step?: number
  depends_on?: any
}

interface WizardStep {
  id: string
  title: string
  description: string
  fields: SetupField[]
}

export default function IntegrationWizard({ integration, mode, onClose }: IntegrationWizardProps) {
  const { t } = useTranslation()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [currentStep, setCurrentStep] = useState(0)
  const [, setSetupSchema] = useState<any>(null)
  const [wizardSteps, setWizardSteps] = useState<WizardStep[]>([])
  const [formData, setFormData] = useState<any>({})
  const [errors, setErrors] = useState<any>({})
  const [showLogs, setShowLogs] = useState(false)
  const [containerId, setContainerId] = useState<string | null>(null)

  useEffect(() => {
    fetchSetupSchema()
  }, [integration])

  const fetchSetupSchema = async () => {
    try {
      const response = await fetch(`/api/integrations/${integration.name}/meta`)
      if (response.ok) {
        const schema = await response.json()
        setSetupSchema(schema)
        
        // Build wizard steps
        const steps: WizardStep[] = []
        
        if (schema.wizard_steps) {
          // Use predefined wizard steps
          schema.wizard_steps.forEach((step: any) => {
            const stepFields = schema.fields.filter((f: any) => f.step === step.id)
            steps.push({
              id: step.id,
              title: step.title,
              description: step.description,
              fields: stepFields
            })
          })
        } else {
          // Create single step with all fields
          steps.push({
            id: 'config',
            title: 'Configuration',
            description: 'Configure your integration',
            fields: schema.fields || []
          })
        }
        
        setWizardSteps(steps)
        
        // Initialize form data with defaults
        const initialData: any = {}
        schema.fields?.forEach((field: SetupField) => {
          if (field.default !== undefined) {
            initialData[field.name] = field.default
          }
        })
        setFormData(initialData)
      }
    } catch (error) {
      console.error('Error fetching setup schema:', error)
      toast({
        title: t('Error'),
        description: t('Failed to load integration setup'),
        variant: 'destructive'
      })
    } finally {
      setLoading(false)
    }
  }

  const validateField = (field: SetupField, value: any): string | null => {
    if (field.required && !value) {
      return `${field.label} is required`
    }
    
    if (field.validation?.pattern) {
      const regex = new RegExp(field.validation.pattern)
      if (!regex.test(value)) {
        return field.validation.message || `Invalid ${field.label}`
      }
    }
    
    if (field.type === 'number') {
      const num = Number(value)
      if (field.min !== undefined && num < field.min) {
        return `${field.label} must be at least ${field.min}`
      }
      if (field.max !== undefined && num > field.max) {
        return `${field.label} must be at most ${field.max}`
      }
    }
    
    return null
  }

  const validateCurrentStep = (): boolean => {
    const currentFields = wizardSteps[currentStep]?.fields || []
    const stepErrors: any = {}
    let isValid = true
    
    currentFields.forEach((field) => {
      // Check dependencies
      if (field.depends_on) {
        const dependsOnField = Object.keys(field.depends_on)[0]
        const dependsOnValue = field.depends_on[dependsOnField]
        if (formData[dependsOnField] !== dependsOnValue) {
          return // Skip validation if dependency not met
        }
      }
      
      const error = validateField(field, formData[field.name])
      if (error) {
        stepErrors[field.name] = error
        isValid = false
      }
    })
    
    setErrors(stepErrors)
    return isValid
  }

  const handleNext = () => {
    if (validateCurrentStep()) {
      if (currentStep < wizardSteps.length - 1) {
        setCurrentStep(currentStep + 1)
      } else {
        handleSubmit()
      }
    }
  }

  const handleBack = () => {
    if (currentStep > 0) {
      setCurrentStep(currentStep - 1)
    }
  }

  const handleSubmit = async () => {
    setSaving(true)
    
    try {
      const payload = {
        instance_id: formData.instance_id || `${integration.name}_default`,
        connector_type: integration.name,
        friendly_name: formData.friendly_name || integration.display_name,
        config: formData,
        devices: [],
        enabled: true,
        update_interval: formData.update_interval || 10
      }
      
      const response = await fetch('/api/instances', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        },
        body: JSON.stringify(payload)
      })
      
      if (response.ok) {
        const result = await response.json()
        
        // Show logs if container ID returned
        if (result.websocket_logs) {
          setContainerId(result.websocket_logs.split('/').pop())
          setShowLogs(true)
        }
        
        toast({
          title: t('Success'),
          description: t('Instance created successfully'),
        })
        
        // Close after a delay to show logs
        setTimeout(() => {
          onClose()
        }, 5000)
      } else {
        const error = await response.json()
        throw new Error(error.detail || 'Failed to create instance')
      }
    } catch (error: any) {
      toast({
        title: t('Error'),
        description: error.message,
        variant: 'destructive'
      })
    } finally {
      setSaving(false)
    }
  }

  const renderField = (field: SetupField) => {
    // Check dependencies
    if (field.depends_on) {
      const dependsOnField = Object.keys(field.depends_on)[0]
      const dependsOnValue = field.depends_on[dependsOnField]
      if (formData[dependsOnField] !== dependsOnValue) {
        return null
      }
    }
    
    const fieldError = errors[field.name]
    
    switch (field.type) {
      case 'text':
      case 'password':
      case 'email':
      case 'ip':
      case 'url':
        return (
          <div key={field.name} className="space-y-2">
            <Label htmlFor={field.name}>
              {field.label}
              {field.required && <span className="text-red-500 ml-1">*</span>}
            </Label>
            <Input
              id={field.name}
              type={field.type === 'password' ? 'password' : 'text'}
              value={formData[field.name] || ''}
              onChange={(e) => setFormData({ ...formData, [field.name]: e.target.value })}
              placeholder={field.placeholder}
              className={fieldError ? 'border-red-500' : ''}
            />
            {field.description && (
              <p className="text-sm text-muted-foreground">{field.description}</p>
            )}
            {fieldError && (
              <p className="text-sm text-red-500">{fieldError}</p>
            )}
          </div>
        )
      
      case 'number':
        return (
          <div key={field.name} className="space-y-2">
            <Label htmlFor={field.name}>
              {field.label}
              {field.required && <span className="text-red-500 ml-1">*</span>}
            </Label>
            <Input
              id={field.name}
              type="number"
              value={formData[field.name] || ''}
              onChange={(e) => setFormData({ ...formData, [field.name]: Number(e.target.value) })}
              min={field.min}
              max={field.max}
              step={field.step}
              className={fieldError ? 'border-red-500' : ''}
            />
            {field.description && (
              <p className="text-sm text-muted-foreground">{field.description}</p>
            )}
            {fieldError && (
              <p className="text-sm text-red-500">{fieldError}</p>
            )}
          </div>
        )
      
      case 'select':
        return (
          <div key={field.name} className="space-y-2">
            <Label htmlFor={field.name}>
              {field.label}
              {field.required && <span className="text-red-500 ml-1">*</span>}
            </Label>
            <Select
              value={formData[field.name] || ''}
              onValueChange={(value: string) => setFormData({ ...formData, [field.name]: value })}
            >
              <SelectTrigger className={fieldError ? 'border-red-500' : ''}>
                <SelectValue placeholder={field.placeholder || `Select ${field.label}`} />
              </SelectTrigger>
              <SelectContent>
                {field.options?.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {field.description && (
              <p className="text-sm text-muted-foreground">{field.description}</p>
            )}
            {fieldError && (
              <p className="text-sm text-red-500">{fieldError}</p>
            )}
          </div>
        )
      
      case 'checkbox':
        return (
          <div key={field.name} className="flex items-start space-x-3 py-2">
            <Checkbox
              id={field.name}
              checked={formData[field.name] || false}
              onCheckedChange={(checked: boolean) => setFormData({ ...formData, [field.name]: checked })}
            />
            <div className="space-y-1">
              <Label htmlFor={field.name} className="cursor-pointer">
                {field.label}
                {field.required && <span className="text-red-500 ml-1">*</span>}
              </Label>
              {field.description && (
                <p className="text-sm text-muted-foreground">{field.description}</p>
              )}
              {fieldError && (
                <p className="text-sm text-red-500">{fieldError}</p>
              )}
            </div>
          </div>
        )
      
      default:
        return null
    }
  }

  if (loading) {
    return (
      <Dialog open={true} onOpenChange={onClose}>
        <DialogContent className="max-w-2xl">
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin" />
          </div>
        </DialogContent>
      </Dialog>
    )
  }

  const currentStepData = wizardSteps[currentStep]
  const progress = ((currentStep + 1) / wizardSteps.length) * 100

  return (
    <Dialog open={true} onOpenChange={onClose}>
      <DialogContent className="max-w-3xl max-h-[80vh] overflow-hidden flex flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-3">
            <div className="text-2xl">{integration.branding?.icon || '⚙️'}</div>
            {mode === 'create' ? t('Add') : t('Edit')} {integration.display_name}
          </DialogTitle>
        </DialogHeader>
        
        {/* Progress Bar */}
        {wizardSteps.length > 1 && (
          <div className="space-y-2">
            <Progress value={progress} className="h-2" />
            <div className="flex justify-between text-sm text-muted-foreground">
              {wizardSteps.map((step, index) => (
                <div
                  key={step.id}
                  className={`flex items-center gap-1 ${
                    index <= currentStep ? 'text-primary font-medium' : ''
                  }`}
                >
                  {index < currentStep && <Check className="h-3 w-3" />}
                  {step.title}
                </div>
              ))}
            </div>
          </div>
        )}
        
        {/* Step Content */}
        <div className="flex-1 overflow-y-auto py-4">
          {!showLogs ? (
            <Card className="border-0 shadow-none">
              <CardHeader>
                <CardTitle>{currentStepData?.title}</CardTitle>
                <CardDescription>{currentStepData?.description}</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {currentStepData?.fields.map(renderField)}
              </CardContent>
            </Card>
          ) : (
            <div className="h-full">
              <h3 className="text-lg font-semibold mb-2">{t('Container Logs')}</h3>
              {containerId && <LogTerminal containerId={containerId} />}
            </div>
          )}
        </div>
        
        {/* Footer */}
        {!showLogs && (
          <div className="flex justify-between pt-4 border-t">
            <Button
              variant="outline"
              onClick={handleBack}
              disabled={currentStep === 0 || saving}
            >
              <ChevronLeft className="mr-2 h-4 w-4" />
              {t('Back')}
            </Button>
            
            <div className="flex gap-2">
              <Button variant="outline" onClick={onClose} disabled={saving}>
                {t('Cancel')}
              </Button>
              <Button onClick={handleNext} disabled={saving}>
                {saving && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {currentStep === wizardSteps.length - 1 ? t('Create Instance') : t('Next')}
                {currentStep < wizardSteps.length - 1 && <ChevronRight className="ml-2 h-4 w-4" />}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  )
}