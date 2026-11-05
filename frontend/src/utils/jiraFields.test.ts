import { describe, expect, it } from 'vitest'
import { mergeProjectFields } from './jiraFields'
import type { JiraField } from '../types/jira'

function field(id: string, overrides: Partial<JiraField> = {}): JiraField {
  return { id, name: id, required: false, control: 'text', schema: {}, allowedValues: [], hasDefaultValue: false, defaultValue: null, ...overrides }
}

describe('shared Jira fields between projects', () => {
  it('preserves text, cleared values, zero and false; defaults new fields and drops removed fields', () => {
    const shared = [field('text'), field('cleared'), field('zero', { control: 'number' }), field('false', { control: 'boolean' })]
    expect(mergeProjectFields([...shared, field('removed')], [...shared, field('new', { defaultValue: 'Default' })], {
      text: 'Typed value', cleared: '', zero: 0, false: false, removed: 'Old',
    })).toEqual({ text: 'Typed value', cleared: '', zero: 0, false: false, new: 'Default' })
  })

  it('preserves shared options by id and removes options missing from the new project', () => {
    const previous = [field('select', { control: 'select' }), field('multi', { control: 'multiselect' })]
    const next = [
      field('select', { control: 'select', allowedValues: [{ id: '1', name: 'Renamed' }] }),
      field('multi', { control: 'multiselect', allowedValues: [{ id: '1' }, { id: '3' }] }),
    ]
    expect(mergeProjectFields(previous, next, { select: { id: '1' }, multi: [{ id: '1' }, { id: '2' }] })).toEqual({ select: { id: '1' }, multi: [{ id: '1' }] })
    expect(mergeProjectFields(previous, next, { select: { id: '2' } }).select).toBeNull()
  })

  it('uses the target default when the field control changes', () => {
    expect(mergeProjectFields([field('same')], [field('same', { control: 'number', defaultValue: 7 })], { same: 'Old text' })).toEqual({ same: 7 })
  })

  it('preserves cascading selections when available and removes unavailable children or parents', () => {
    const previous = [field('cascade', { control: 'cascade' })]
    const next = [field('cascade', { control: 'cascade', allowedValues: [{ id: '1', children: [{ id: '2' }] }] })]
    expect(mergeProjectFields(previous, next, { cascade: { id: '1', child: { id: '2' } } }).cascade).toEqual({ id: '1', child: { id: '2' } })
    expect(mergeProjectFields(previous, next, { cascade: { id: '1', child: { id: '3' } } }).cascade).toEqual({ id: '1' })
    expect(mergeProjectFields(previous, next, { cascade: { id: '9' } }).cascade).toBeNull()
  })
})
