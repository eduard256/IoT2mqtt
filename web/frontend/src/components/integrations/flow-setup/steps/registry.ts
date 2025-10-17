import type { StepDefinition } from '../types'

class StepRegistry {
  private steps = new Map<string, StepDefinition>()

  register(definition: StepDefinition): void {
    if (this.steps.has(definition.type)) {
      console.warn(`Step type "${definition.type}" is already registered`)
      return
    }
    this.steps.set(definition.type, definition)
  }

  getStep(type: string): StepDefinition | null {
    return this.steps.get(type) || null
  }

  getAvailableTypes(): string[] {
    return Array.from(this.steps.keys())
  }

  getAllSteps(): StepDefinition[] {
    return Array.from(this.steps.values())
  }
}

export const stepRegistry = new StepRegistry()
