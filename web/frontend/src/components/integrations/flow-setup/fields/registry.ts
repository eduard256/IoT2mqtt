import type { FieldDefinition } from '../types'

class FieldRegistry {
  private standardFields = new Map<string, FieldDefinition>()
  private customFields = new Map<string, FieldDefinition>()

  registerStandard(definition: FieldDefinition): void {
    if (this.standardFields.has(definition.type)) {
      console.warn(`Standard field type "${definition.type}" is already registered`)
      return
    }
    this.standardFields.set(definition.type, definition)
  }

  registerCustom(definition: FieldDefinition): void {
    if (this.customFields.has(definition.type)) {
      console.warn(`Custom field type "${definition.type}" is already registered`)
      return
    }
    this.customFields.set(definition.type, definition)
  }

  getField(type: string, connectorName?: string): FieldDefinition | null {
    // Check custom fields first (higher priority)
    const customField = this.customFields.get(type)
    if (customField) {
      // Check if this field is available for this connector
      if (!customField.connectors || customField.connectors.includes(connectorName || '')) {
        return customField
      }
    }

    // Fall back to standard fields
    return this.standardFields.get(type) || null
  }

  getAvailableTypes(connectorName?: string): string[] {
    const types = new Set<string>()

    // Add all standard field types
    for (const [type] of this.standardFields) {
      types.add(type)
    }

    // Add custom fields available for this connector
    for (const [type, def] of this.customFields) {
      if (!def.connectors || def.connectors.includes(connectorName || '')) {
        types.add(type)
      }
    }

    return Array.from(types)
  }

  getAllFields(): FieldDefinition[] {
    return [
      ...Array.from(this.standardFields.values()),
      ...Array.from(this.customFields.values())
    ]
  }
}

export const fieldRegistry = new FieldRegistry()
