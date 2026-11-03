import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import JiraDynamicField from './JiraDynamicField.vue'
import { dynamicFields, initialFieldValue, isEmptyField } from '../../../utils/jiraFields'
import type { JiraField } from '../../../types/jira'

function field(overrides: Partial<JiraField> = {}): JiraField {
  return { id: 'customfield_100', name: 'Business unit', required: true, control: 'text', schema: { type: 'string' }, allowedValues: [], hasDefaultValue: false, defaultValue: null, ...overrides }
}

describe('Jira create-screen fields', () => {
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
