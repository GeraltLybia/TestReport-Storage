import type { JiraField } from '../types/jira'

export const builtinFields = new Set(['project', 'issuetype', 'summary', 'description', 'reporter', 'attachment', 'priority', 'components', 'labels', 'assignee', 'environment'])

export function isEmptyField(value: unknown): boolean {
  return value == null || (typeof value === 'string' && !value.trim()) || (Array.isArray(value) && !value.length) || (typeof value === 'object' && !Object.keys(value).length)
}

export function hasFixedDefault(field: JiraField): boolean {
  return field.defaultValue != null && field.allowedValues.length === 0
}

export function defaultFieldLabel(field: JiraField): string {
  const label = (value: unknown): string => {
    if (value === true) return 'Да'
    if (value === false) return 'Нет'
    if (value && typeof value === 'object') {
      const text = optionLabel(value)
      const child = (value as Record<string, unknown>).child
      return child ? `${text} / ${label(child)}` : text || JSON.stringify(value)
    }
    return String(value ?? '')
  }
  return Array.isArray(field.defaultValue) ? field.defaultValue.map(label).join(', ') : label(field.defaultValue)
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

/** Keep shared fields, including deliberately cleared values; default only new fields. */
export function mergeProjectFields(previous: JiraField[], next: JiraField[], values: Record<string, unknown>): Record<string, unknown> {
  return Object.fromEntries(dynamicFields(next).map(field => {
    const shared = previous.some(old => old.id === field.id && old.control === field.control)
    let value = !hasFixedDefault(field) && shared && field.id in values ? values[field.id] : initialFieldValue(field)
    if (shared && field.allowedValues.length) {
      if (field.control === 'select' && !field.allowedValues.some(option => sameOption(option, value))) value = null
      if (field.control === 'multiselect' && Array.isArray(value)) {
        value = value.filter(item => field.allowedValues.some(option => sameOption(option, item)))
      }
      if (field.control === 'cascade' && value && typeof value === 'object') {
        const option = field.allowedValues.find(option => sameOption(option, value)) as Record<string, unknown> | undefined
        if (!option) value = null
        else {
          const child = (value as Record<string, unknown>).child
          if (child && !(Array.isArray(option.children) && option.children.some(item => sameOption(item, child)))) value = optionValue(option)
        }
      }
    }
    return [field.id, value]
  }))
}
