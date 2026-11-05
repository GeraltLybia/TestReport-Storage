import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import BugCreateDialog from './BugCreateDialog.vue'
import { createBug, fetchBugDraft, fetchJiraMeta, previewBug } from '../../../api/jira'
import { fetchReportResults } from '../../../api/reports'
import type { BugDraft, JiraField, JiraMeta } from '../../../types/jira'

vi.mock('../../../api/jira', () => ({
  createBug: vi.fn(), commentBug: vi.fn(), fetchBugDraft: vi.fn(), fetchJiraMeta: vi.fn(), previewBug: vi.fn(),
}))
vi.mock('../../../api/reports', () => ({ fetchReportResults: vi.fn() }))

let wrapper: VueWrapper

beforeEach(async () => {
  vi.resetAllMocks()
  vi.mocked(fetchReportResults).mockResolvedValue({ items: [] } as unknown as Awaited<ReturnType<typeof fetchReportResults>>)
  vi.mocked(fetchBugDraft).mockResolvedValue({
    report: { id: 'report-1', name: 'Run' },
    test: { id: 'test-1', parameters: [] }, error: { message: 'Failure' },
    sections: [], defaultSteps: [], attachments: [],
    suggested: { summary: 'Original title', labels: [] },
    duplicates: { exact: null, similar: [] }, links: {},
  } as unknown as BugDraft)
  vi.mocked(fetchJiraMeta).mockResolvedValue({
    projectKey: 'QA', issueType: { id: '1', name: 'Bug' }, fields: ['summary'], fieldDefinitions: [], unsupportedRequired: [],
    components: [], priorities: [], defaultPriority: null,
  } as unknown as JiraMeta)
  vi.mocked(previewBug).mockResolvedValue({ description: 'h3. Шаги\n# Первый шаг', steps: 1, logLines: 0 })
  vi.mocked(createBug).mockResolvedValue({ key: 'QA-1' } as Awaited<ReturnType<typeof createBug>>)
  wrapper = mount(BugCreateDialog, {
    props: {
      reportId: 'report-1', initialTestId: 'test-1', context: 'Run', links: {},
      config: { enabled: true, baseUrl: 'https://jira.example', projectKey: 'QA', issueType: 'Bug' },
    },
    global: { stubs: { teleport: true } },
    attachTo: document.body,
  })
  await flushPromises()
})

afterEach(() => { wrapper.unmount() })

async function openReview() {
  await wrapper.get('#bug-expected').setValue('Expected result')
  await wrapper.get('.bug-footer .bug-btn--primary').trigger('click')
  await flushPromises()
}

describe('bug review before filing', () => {
  it('keeps a single configured project fixed and uses it when filing', async () => {
    expect(wrapper.find('[aria-label="Проект Jira"]').exists()).toBe(false)
    expect(fetchJiraMeta).toHaveBeenCalledExactlyOnceWith('QA', expect.any(AbortSignal))
    await openReview()
    await wrapper.get('.bug-btn--primary').trigger('click')
    await flushPromises()
    expect(createBug).toHaveBeenCalledWith(expect.objectContaining({ projectKey: 'QA' }))
  })
  it('requires the expected result before preparing the final text', async () => {
    await wrapper.get('.bug-footer .bug-btn--primary').trigger('click')
    expect(wrapper.text()).toContain('Опишите ожидаемый результат')
    expect(previewBug).not.toHaveBeenCalled()
    expect(createBug).not.toHaveBeenCalled()
  })

  it('loads Jira markup and only sends the edited title and text after confirmation', async () => {
    await openReview()
    expect(createBug).not.toHaveBeenCalled()
    expect(wrapper.get('textarea').element.value).toBe('h3. Шаги\n# Первый шаг')
    await wrapper.get('input').setValue('Edited title')
    await wrapper.get('textarea').setValue('h3. Исправлено\n*Итоговый текст*')
    await wrapper.get('.bug-btn--primary').trigger('click')
    await flushPromises()
    expect(createBug).toHaveBeenCalledExactlyOnceWith(expect.objectContaining({
      reportId: 'report-1', testId: 'test-1', expected: 'Expected result',
      summary: 'Edited title', description: 'h3. Исправлено\n*Итоговый текст*',
    }))
    expect(wrapper.emitted('filed')).toHaveLength(1)
  })

  it('returns to the form without sending and rebuilds markup from the updated form', async () => {
    await openReview()
    await wrapper.get('.bug-footer .bug-btn').trigger('click')
    expect(wrapper.get<HTMLTextAreaElement>('#bug-expected').element.value).toBe('Expected result')
    await wrapper.get('#bug-expected').setValue('Updated expected result')
    await wrapper.get('.bug-btn--primary').trigger('click')
    await flushPromises()
    expect(previewBug).toHaveBeenLastCalledWith(expect.objectContaining({ expected: 'Updated expected result' }))
    expect(createBug).not.toHaveBeenCalled()
  })

  it('keeps edits after a Jira error and prevents sending an empty description', async () => {
    await openReview()
    await wrapper.get('textarea').setValue('   ')
    expect(wrapper.get('.bug-btn--primary').attributes('disabled')).toBeDefined()
    await wrapper.get('textarea').setValue('h3. My changes')
    vi.mocked(createBug).mockRejectedValueOnce(new Error('Jira unavailable'))
    await wrapper.get('.bug-btn--primary').trigger('click')
    await flushPromises()
    expect(wrapper.get('[role="alert"]').text()).toBe('Jira unavailable')
    expect(wrapper.get('textarea').element.value).toBe('h3. My changes')
    await wrapper.get('.bug-btn--primary').trigger('click')
    await flushPromises()
    expect(createBug).toHaveBeenCalledTimes(2)
  })

  it('stays in the form when markup generation fails', async () => {
    vi.mocked(previewBug).mockRejectedValueOnce(new Error('Preview unavailable'))
    await openReview()
    expect(wrapper.find('#bug-expected').exists()).toBe(true)
    expect(wrapper.get('[role="alert"]').text()).toBe('Preview unavailable')
    expect(createBug).not.toHaveBeenCalled()
  })
})

function textField(id: string, defaultValue: unknown = null): JiraField {
  return { id, name: id, required: false, control: 'text', schema: { type: 'string' }, allowedValues: [], hasDefaultValue: defaultValue !== null, defaultValue }
}

function projectMeta(projectKey: string, fields: JiraField[]): JiraMeta {
  return {
    projectKey, issueType: { id: projectKey === 'QA' ? '1' : '2', name: 'Bug' },
    fields: ['summary', ...fields.map(field => field.id)], fieldDefinitions: fields,
    unsupportedRequired: [], components: [], priorities: [], defaultPriority: null,
  }
}

async function enableProjects() {
  await wrapper.setProps({ config: { enabled: true, baseUrl: 'https://jira.example', projectKey: 'QA', projectKeys: ['QA', 'CORE', 'APP'], issueType: 'Bug' } })
}

describe('Jira project switching', () => {
  it('preserves shared priority, components, labels and assignee', async () => {
    const fields = [textField('priority'), textField('components'), textField('labels'), textField('assignee')]
    const source = {
      ...projectMeta('CORE', fields),
      priorities: [{ id: '1', name: 'High' }, { id: '2', name: 'Low' }], defaultPriority: '2',
      components: [{ id: '10', name: 'Shared' }, { id: '20', name: 'CORE only' }],
    }
    vi.mocked(fetchJiraMeta).mockResolvedValueOnce(source)
    await enableProjects()
    await wrapper.get('[aria-label="Проект Jira"]').setValue('CORE')
    await flushPromises()
    const label = (name: string) => wrapper.findAll('label').find(item => item.find('.bug-label').exists() && item.get('.bug-label').text() === name)!
    await label('Приоритет').get('select').setValue('1')
    await label('Исполнитель').get('input').setValue('alice')
    await wrapper.get('[aria-label="Добавить компонент"]').setValue('10')
    await wrapper.get('[aria-label="Добавить компонент"]').setValue('20')
    await wrapper.get('.bug-chip-input').setValue('user-label')
    await wrapper.get('.bug-chip-input').trigger('keydown', { key: 'Enter' })
    vi.mocked(fetchJiraMeta).mockResolvedValueOnce({
      ...source, projectKey: 'APP', components: [{ id: '10', name: 'Shared' }],
    })
    await wrapper.get('[aria-label="Проект Jira"]').setValue('APP')
    await flushPromises()
    expect(label('Приоритет').get<HTMLSelectElement>('select').element.value).toBe('1')
    expect(label('Исполнитель').get<HTMLInputElement>('input').element.value).toBe('alice')
    await openReview()
    await wrapper.get('.bug-btn--primary').trigger('click')
    await flushPromises()
    expect(createBug).toHaveBeenCalledWith(expect.objectContaining({
      projectKey: 'APP', priority: '1', components: ['10'], labels: ['user-label'], assignee: 'alice',
    }))
  })

  it('reloads fields, retains shared input and sends the selected project and its fields', async () => {
    const shared = textField('customfield_shared')
    vi.mocked(fetchJiraMeta).mockResolvedValueOnce(projectMeta('CORE', [shared, textField('customfield_old')]))
    await enableProjects()
    await wrapper.get('[aria-label="Проект Jira"]').setValue('CORE')
    await flushPromises()
    await wrapper.get('#jira-customfield_shared').setValue('Keep me')
    await wrapper.get('#jira-customfield_old').setValue('Only CORE')
    vi.mocked(fetchJiraMeta).mockResolvedValueOnce(projectMeta('APP', [shared, textField('customfield_new', 'New default')]))
    await wrapper.get('[aria-label="Проект Jira"]').setValue('APP')
    await flushPromises()
    expect(fetchJiraMeta).toHaveBeenLastCalledWith('APP', expect.any(AbortSignal))
    expect(wrapper.get<HTMLInputElement>('#jira-customfield_shared').element.value).toBe('Keep me')
    expect(wrapper.find('#jira-customfield_old').exists()).toBe(false)
    expect(wrapper.get<HTMLInputElement>('#jira-customfield_new').element.value).toBe('New default')
    await openReview()
    expect(wrapper.text()).toContain('Проект APP')
    await wrapper.get('.bug-btn--primary').trigger('click')
    await flushPromises()
    expect(createBug).toHaveBeenCalledWith(expect.objectContaining({
      projectKey: 'APP', summary: 'Original title', expected: 'Expected result',
      extraFields: { customfield_shared: 'Keep me', customfield_new: 'New default' },
    }))
  })

  it('ignores obsolete responses after a quick switch and blocks filing while loading', async () => {
    let resolveOld!: (meta: JiraMeta) => void
    vi.mocked(fetchJiraMeta).mockReturnValueOnce(new Promise(resolve => { resolveOld = resolve }))
    await enableProjects()
    await wrapper.get('[aria-label="Проект Jira"]').setValue('CORE')
    expect(wrapper.get('.bug-btn--primary').attributes('disabled')).toBeDefined()
    const calls = vi.mocked(fetchJiraMeta).mock.calls
    const oldSignal = calls[calls.length - 1]?.[1]
    vi.mocked(fetchJiraMeta).mockResolvedValueOnce(projectMeta('APP', [textField('customfield_app')]))
    await wrapper.get('[aria-label="Проект Jira"]').setValue('APP')
    await flushPromises()
    expect(oldSignal?.aborted).toBe(true)
    resolveOld(projectMeta('CORE', [textField('customfield_core')]))
    await flushPromises()
    expect(wrapper.find('#jira-customfield_app').exists()).toBe(true)
    expect(wrapper.find('#jira-customfield_core').exists()).toBe(false)
  })

  it('blocks filing after a project load error and permits retrying the selected project', async () => {
    await enableProjects()
    vi.mocked(fetchJiraMeta).mockRejectedValueOnce(new Error('Project unavailable'))
    await wrapper.get('[aria-label="Проект Jira"]').setValue('CORE')
    await flushPromises()
    expect(wrapper.text()).toContain('Project unavailable')
    expect(wrapper.get('.bug-btn--primary').attributes('disabled')).toBeDefined()
    vi.mocked(fetchJiraMeta).mockResolvedValueOnce(projectMeta('CORE', [textField('customfield_core')]))
    const retry = wrapper.findAll('button').find(button => button.text() === 'Повторить загрузку полей')!
    await retry.trigger('click')
    await flushPromises()
    expect(wrapper.find('#jira-customfield_core').exists()).toBe(true)
    expect(wrapper.get('.bug-btn--primary').attributes('disabled')).toBeUndefined()
    expect(createBug).not.toHaveBeenCalled()
  })

  it('validates newly required fields after switching', async () => {
    await enableProjects()
    vi.mocked(fetchJiraMeta).mockResolvedValueOnce(projectMeta('CORE', [{ ...textField('customfield_required'), required: true }]))
    await wrapper.get('[aria-label="Проект Jira"]').setValue('CORE')
    await flushPromises()
    await openReview()
    expect(wrapper.get('[role="alert"]').text()).toContain('customfield_required')
    expect(previewBug).not.toHaveBeenCalled()
    await wrapper.get('#jira-customfield_required').setValue('Required value')
    await wrapper.get('.bug-btn--primary').trigger('click')
    await flushPromises()
    expect(previewBug).toHaveBeenCalledOnce()
  })
})
