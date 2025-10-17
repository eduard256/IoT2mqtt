import { useCallback } from 'react'
import type { FlowContext } from '../types'

export function useTemplateResolver(context: FlowContext) {
  const resolveTemplate = useCallback(
    (value: unknown, extra: Record<string, unknown> = {}): any => {
      if (typeof value !== 'string') return value

      const combined = { ...context, ...extra }

      // Single template placeholder {{ path }}
      const singleMatch = value.match(/^{{\s*([^}]+)\s*}}$/)
      if (singleMatch) {
        const rawPath = singleMatch[1]
        const segments = rawPath
          .split('.')
          .map(segment => segment.trim())
          .filter(segment => segment)

        let pointer: any = combined
        for (const segment of segments) {
          if (pointer == null) return ''
          pointer = pointer[segment]
        }
        return pointer ?? ''
      }

      // Multiple placeholders in string
      const matcher = /{{\s*([^}]+)\s*}}/g
      return value.replace(matcher, (_, rawPath) => {
        const path = rawPath.trim()
        const segments = path
          .split('.')
          .map(segment => segment.trim())
          .filter(segment => segment)

        let pointer: any = combined
        for (const segment of segments) {
          if (pointer == null) return ''
          pointer = pointer[segment]
        }

        if (pointer == null) return ''
        if (typeof pointer === 'object') return JSON.stringify(pointer)
        return String(pointer)
      })
    },
    [context]
  )

  const resolveDeep = useCallback(
    <T = any>(payload: T, extra: Record<string, unknown> = {}): T => {
      if (payload == null) return payload

      if (typeof payload === 'string') {
        return resolveTemplate(payload, extra) as T
      }

      if (Array.isArray(payload)) {
        return payload.map(item => resolveDeep(item, extra)) as T
      }

      if (typeof payload === 'object') {
        const result: Record<string, any> = {}
        for (const [key, val] of Object.entries(payload)) {
          result[key] = resolveDeep(val, extra)
        }
        return result as T
      }

      return payload
    },
    [resolveTemplate]
  )

  return { resolveTemplate, resolveDeep }
}
