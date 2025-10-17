export function readContextPath(context: any, path: string): any {
  const segments = path
    .split('.')
    .map(segment => segment.trim())
    .filter(segment => segment)

  let cursor: any = context
  for (const segment of segments) {
    if (cursor == null) return undefined
    cursor = cursor[segment as keyof typeof cursor]
  }
  return cursor
}

export function evaluateConditions(
  conditions: Record<string, unknown> | undefined,
  context: any,
  resolveTemplate: (value: unknown) => any
): boolean {
  if (!conditions) return true

  return Object.entries(conditions).every(([path, expected]) => {
    const actual = readContextPath(context, path)
    const expectedValue = typeof expected === 'string' ? resolveTemplate(expected) : expected

    if (Array.isArray(expectedValue)) {
      return Array.isArray(actual) && expectedValue.every(item => actual.includes(item))
    }

    return actual === expectedValue
  })
}
