import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import JiraDynamicField from './JiraDynamicField.vue'
import { dynamicFields, initialFieldValue, isEmptyField } from '../../../utils/jiraFields'
import type { JiraField } from '../../../types/jira'

function field(overrides: Partial<JiraField> = {}): JiraField {
  return { id: 'customfield_100', name: 'Business unit', required: true, control: 'text', schema: { type: 'string' }, allowedValues: [], hasDefaultValue: false, defaultValue: null, ...overrides }
}

describe('Jira create-screen fields', () => {
  it.each([
    ['text', 'Default text', 'Default text'],
    ['number', 0, '0'],
    ['boolean', false, 'Нет'],
    ['user', { name: 'alice', displayName: 'Alice' }, 'Alice'],
    ['select', { id: '10', value: 'Default option' }, 'Default option'],
    ['multiselect', [{ id: '10', name: 'First' }, { id: '20', name: 'Second' }], 'First, Second'],
  ] as const)('shows a read-only default for %s without allowed values', (control, defaultValue, label) => {
    const definition = field({ control, defaultValue, hasDefaultValue: true })
    const wrapper = mount(JiraDynamicField, { props: { field: definition } })
    const input = wrapper.get('input')
    expect(input.attributes('readonly')).toBeDefined()
    expect(input.element.value).toBe(label)
    expect(wrapper.text()).toContain('Значение по умолчанию из Jira')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([initialFieldValue(definition)])
  })

  it('keeps a field editable when only the default flag is present', () => {
    const wrapper = mount(JiraDynamicField, { props: { field: field({ hasDefaultValue: true, defaultValue: null }) } })
    expect(wrapper.get('input').attributes('readonly')).toBeUndefined()
  })

  it('updates a fixed default when switching projects and unlocks a field with options', async () => {
    const wrapper = mount(JiraDynamicField, { props: { field: field({ defaultValue: 'First' }) } })
    await wrapper.setProps({ field: field({ defaultValue: 'Second' }) })
    expect(wrapper.get('input').element.value).toBe('Second')
    const defaults = wrapper.emitted('update:modelValue')!
    expect(defaults[defaults.length - 1]).toEqual(['Second'])
    await wrapper.setProps({ field: field({ control: 'select', defaultValue: { id: '10' }, allowedValues: [{ id: '10' }, { id: '20' }] }) })
    expect(wrapper.get('select').attributes('disabled')).toBeUndefined()
    await wrapper.get('select').setValue('1')
    const events = wrapper.emitted('update:modelValue')!
    expect(events[events.length - 1]).toEqual([{ id: '20' }])
  })

  it('shows a required field and its validation message', () => {
    const wrapper = mount(JiraDynamicField, { props: { field: field(), invalid: true } })
    expect(wrapper.get('label').text()).toBe('Business unit *')
    expect(wrapper.get('input').attributes('aria-required')).toBe('true')
    expect(wrapper.text()).toContain('Заполните обязательное поле')
  })

  it('sends an option id, not its display label or metadata', async () => {
    const wrapper = mount(JiraDynamicField, { props: { field: field({ control: 'select', allowedValues: [{ id: '10', value: 'Retail', self: '/option/10' }] }) } })
    await wrapper.get('select').setValue('0')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([{ id: '10' }])
  })

  it('supports multiple version ids and defaults', async () => {
    const definition = field({ control: 'multiselect', allowedValues: [{ id: '10', name: '1.0' }, { id: '20', name: '2.0' }], defaultValue: [{ id: '10', name: '1.0' }] })
    const wrapper = mount(JiraDynamicField, { props: { field: definition, modelValue: initialFieldValue(definition) } })
    expect((wrapper.get('select').element as HTMLSelectElement).selectedOptions[0]?.text).toBe('1.0')
    await wrapper.get('select').setValue(['0', '1'])
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([[{ id: '10' }, { id: '20' }]])
  })

  it('keeps the parent id and adds the chosen cascade child', async () => {
    const wrapper = mount(JiraDynamicField, { props: { field: field({ control: 'cascade', allowedValues: [{ id: '10', value: 'Region', children: [{ id: '11', value: 'City' }] }] }), modelValue: { id: '10' } } })
    await wrapper.get('#jira-customfield_100-child').setValue('0')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([{ id: '10', child: { id: '11' } }])
  })

  it('does not mistake zero or false for a missing required value', async () => {
    expect(isEmptyField(0)).toBe(false)
    expect(isEmptyField(false)).toBe(false)
    const wrapper = mount(JiraDynamicField, { props: { field: field({ control: 'number' }) } })
    await wrapper.get('input').setValue('0')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([0])
  })

  it('accepts several user logins typed with commas', async () => {
    const wrapper = mount(JiraDynamicField, { props: { field: field({ control: 'users' }) } })
    const input = wrapper.get('input')
    await input.setValue('alice, bob')
    await input.trigger('change')
    expect(wrapper.emitted('update:modelValue')?.[0]).toEqual([[{ name: 'alice' }, { name: 'bob' }]])
  })

  it('does not expose generated fields or unknown plugin editors as text inputs', () => {
    const fields = [field({ id: 'project' }), field({ id: 'customfield_plugin', control: 'unsupported' }), field()]
    expect(dynamicFields(fields).map(f => f.id)).toEqual(['customfield_100'])
  })
})
