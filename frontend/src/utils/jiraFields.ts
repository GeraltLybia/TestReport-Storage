import type { JiraField } from '../types/jira'

export const builtinFields = new Set(['project', 'issuetype', 'summary', 'description', 'reporter', 'attachment', 'priority', 'components', 'labels', 'assignee', 'environment'])

export function isEmptyField(value: unknown): boolean {
  return value == null || (typeof value === 'string' && !value.trim()) || (Array.isArray(value) && !value.length) || (typeof value === 'object' && !Object.keys(value).length)
}

export function optionValue(value: unknown): unknown {
  if (value && typeof value === 'object') {
    const obj = value as Record<string, unknown>
    for (const key of ['id', 'name', 'value', 'key']) {
      if (obj[key] != null) return { [key]: obj[key] }
    }
  }
  return value
}

export function optionLabel(value: unknown): string {
  if (value && typeof value === 'object') {
    const obj = value as Record<string, unknown>
    return String(obj.value ?? obj.displayName ?? obj.name ?? obj.id ?? obj.key ?? '')
  }
  return String(value)
}

export function sameOption(a: unknown, b: unknown): boolean {
  return JSON.stringify(optionValue(a)) === JSON.stringify(optionValue(b))
}

export function initialFieldValue(field: JiraField): unknown {
  const value = field.defaultValue
  if (value == null) return field.control === 'multiselect' ? [] : null
  if (field.control === 'multiselect' && Array.isArray(value)) return value.map(optionValue)
  if (field.control === 'cascade' && typeof value === 'object') {
    const child = (value as Record<string, unknown>).child
    return { ...(optionValue(value) as object), ...(child ? { child: optionValue(child) } : {}) }
  }
  if (field.control === 'select') return optionValue(value)
  return value
}

export function dynamicFields(fields: JiraField[]): JiraField[] {
  return fields.filter(f => !builtinFields.has(f.id) && f.control !== 'unsupported')
}
