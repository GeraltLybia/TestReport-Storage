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

function mountDialog() {
  return mount(BugCreateDialog, {
    props: {
      reportId: 'report-1', initialTestId: 'test-1', context: 'Run', links: {},
      config: { enabled: true, baseUrl: 'https://jira.example', projectKey: 'QA', issueType: 'Bug' },
    },
    global: { stubs: { teleport: true } },
    attachTo: document.body,
  })
}

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
  wrapper = mountDialog()
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
    const original = HTMLElement.prototype.scrollIntoView
    const scroll = vi.fn()
    HTMLElement.prototype.scrollIntoView = scroll
    try {
      await wrapper.get('.bug-footer .bug-btn--primary').trigger('click')
      await flushPromises()
      expect(wrapper.text()).toContain('Опишите ожидаемый результат')
      expect(document.activeElement).toBe(wrapper.get('#bug-expected').element)
      expect(scroll).toHaveBeenCalledWith({ behavior: 'smooth', block: 'center' })
    } finally {
      HTMLElement.prototype.scrollIntoView = original
    }
    expect(previewBug).not.toHaveBeenCalled()
    expect(createBug).not.toHaveBeenCalled()
  })

  it('opens the preview tab and focuses an empty expected result when markup is displayed', async () => {
    await wrapper.findAll('button').find(button => button.text() === 'Разметка Jira')!.trigger('click')
    expect(wrapper.find('#bug-expected').exists()).toBe(false)
    await wrapper.get('.bug-footer .bug-btn--primary').trigger('click')
    await flushPromises()
    expect(document.activeElement).toBe(wrapper.get('#bug-expected').element)
    expect(wrapper.get('#bug-expected').attributes('aria-invalid')).toBe('true')
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

describe('test author as Jira assignee', () => {
  async function remountWithAuthor(defaultName: string, authorFound = true, lateMeta = false) {
    const draft = await vi.mocked(fetchBugDraft).mock.results[0]!.value as BugDraft
    wrapper.unmount()
    vi.mocked(fetchBugDraft).mockResolvedValueOnce({
      ...draft, suggested: { ...draft.suggested, assignee: { name: 'test-author', displayName: 'Test Author', found: authorFound } },
    })
    const metadata = projectMeta('QA', [{
      ...textField('assignee', { name: defaultName }), control: 'user', required: true,
    }])
    let resolveMeta!: (value: JiraMeta) => void
    if (lateMeta) vi.mocked(fetchJiraMeta).mockReturnValueOnce(new Promise(resolve => { resolveMeta = resolve }))
    else vi.mocked(fetchJiraMeta).mockResolvedValueOnce(metadata)
    wrapper = mountDialog()
    await flushPromises()
    if (lateMeta) {
      resolveMeta(metadata)
      await flushPromises()
    }
  }

  it.each([
    ['-1', false], ['-1', true], ['jira-default', false], ['jira-default', true],
  ] as const)('keeps the author instead of default %s with late metadata=%s', async (defaultName, lateMeta) => {
    await remountWithAuthor(defaultName, true, lateMeta)
    expect(wrapper.get<HTMLInputElement>('#bug-assignee').element.value).toBe('test-author')
    expect(wrapper.get('#bug-assignee').attributes('readonly')).toBeUndefined()
    expect(wrapper.text()).toContain('Test Author · автор теста')
    await openReview()
    await wrapper.get('.bug-btn--primary').trigger('click')
    await flushPromises()
    expect(createBug).toHaveBeenCalledWith(expect.objectContaining({ assignee: 'test-author' }))
  })

  it('keeps manual assignee edits after switching to a project with default -1', async () => {
    await remountWithAuthor('-1')
    await wrapper.get('#bug-assignee').setValue('manual-user')
    await enableProjects()
    vi.mocked(fetchJiraMeta).mockResolvedValueOnce(projectMeta('CORE', [{
      ...textField('assignee', { name: '-1' }), control: 'user', required: true,
    }]))
    await wrapper.get('[aria-label="Проект Jira"]').setValue('CORE')
    await flushPromises()
    expect(wrapper.get<HTMLInputElement>('#bug-assignee').element.value).toBe('manual-user')
    await openReview()
    await wrapper.get('.bug-btn--primary').trigger('click')
    await flushPromises()
    expect(createBug).toHaveBeenCalledWith(expect.objectContaining({ projectKey: 'CORE', assignee: 'manual-user' }))
  })

  it('does not put the -1 sentinel into the form if the author is not found', async () => {
    await remountWithAuthor('-1', false)
    expect(wrapper.get<HTMLInputElement>('#bug-assignee').element.value).toBe('')
    expect(wrapper.text()).toContain('В Jira нет пользователя «test-author»')
  })
})

describe('Jira project switching', () => {
  it('uses target fixed defaults for shared custom and built-in fields and submits them', async () => {
    await enableProjects()
    vi.mocked(fetchJiraMeta).mockResolvedValueOnce(projectMeta('CORE', [
      { ...textField('customfield_shared'), required: true },
    ]))
    await wrapper.get('[aria-label="Проект Jira"]').setValue('CORE')
    await flushPromises()
    await wrapper.get('#jira-customfield_shared').setValue('Previous input')
    vi.mocked(fetchJiraMeta).mockResolvedValueOnce(projectMeta('APP', [
      { ...textField('customfield_shared', 'APP default'), required: true },
      { ...textField('assignee', { name: 'alice', displayName: 'Alice' }), control: 'user', required: true },
      { ...textField('priority', { id: '1', name: 'High' }), control: 'select', required: true },
    ]))
    await wrapper.get('[aria-label="Проект Jira"]').setValue('APP')
    await flushPromises()
    expect(wrapper.get<HTMLInputElement>('#jira-customfield_shared').element.value).toBe('APP default')
    expect(wrapper.get('#jira-customfield_shared').attributes('readonly')).toBeDefined()
    expect(wrapper.get<HTMLInputElement>('#bug-assignee').element.value).toBe('alice')
    expect(wrapper.get('#bug-assignee').attributes('readonly')).toBeUndefined()
    expect(wrapper.get<HTMLInputElement>('#jira-priority').element.value).toBe('High')
    await openReview()
    await wrapper.get('.bug-btn--primary').trigger('click')
    await flushPromises()
    expect(createBug).toHaveBeenCalledWith(expect.objectContaining({
      projectKey: 'APP', assignee: 'alice', priority: '1', extraFields: { customfield_shared: 'APP default' },
    }))
  })

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
    await wrapper.get('[aria-controls="bug-issue-fields"]').trigger('click')
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
    await wrapper.get('[aria-controls="bug-issue-fields"]').trigger('click')
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

describe('optional Jira fields', () => {
  async function loadFields() {
    await enableProjects()
    vi.mocked(fetchJiraMeta).mockResolvedValueOnce({ ...projectMeta('CORE', [
      { ...textField('customfield_required'), required: true },
      textField('customfield_optional'),
      { ...textField('priority'), required: true },
      textField('assignee'),
    ]), priorities: [{ id: '1', name: 'High' }], defaultPriority: '1' })
    await wrapper.get('[aria-label="Проект Jira"]').setValue('CORE')
    await flushPromises()
  }

  it('hides optional built-in and custom fields by default and keeps required fields visible', async () => {
    await loadFields()
    expect(wrapper.get('#jira-customfield_required').isVisible()).toBe(true)
    expect(wrapper.get('#jira-customfield_optional').isVisible()).toBe(false)
    const fields = wrapper.findAll('.bug-field')
    expect(fields.find(field => field.find('.bug-label').exists() && field.get('.bug-label').text() === 'Приоритет *')?.isVisible()).toBe(true)
    expect(fields.find(field => field.find('.bug-label').exists() && field.get('.bug-label').text() === 'Исполнитель')?.isVisible()).toBe(false)
    const toggle = wrapper.get('[aria-controls="bug-issue-fields"]')
    expect(toggle.attributes('aria-expanded')).toBe('false')
    expect(toggle.text()).toContain('(2)')
    await toggle.trigger('click')
    expect(wrapper.get('#jira-customfield_optional').isVisible()).toBe(true)
    expect(wrapper.get('[aria-controls="bug-issue-fields"]').attributes('aria-expanded')).toBe('true')
    expect(wrapper.findAll('.bug-field').find(field => field.find('.bug-label').exists() && field.get('.bug-label').text() === 'Исполнитель')?.isVisible()).toBe(true)
  })

  it('preserves optional input when hidden and sends it together with required fields', async () => {
    await loadFields()
    const toggle = wrapper.get('[aria-controls="bug-issue-fields"]')
    await toggle.trigger('click')
    await wrapper.get('#jira-customfield_optional').setValue('Keep optional text')
    const assignee = wrapper.findAll('label').find(label => label.find('.bug-label').exists() && label.get('.bug-label').text() === 'Исполнитель')!.get('input')
    await assignee.setValue('alice')
    await toggle.trigger('click')
    expect(wrapper.get('#jira-customfield_optional').isVisible()).toBe(false)
    await toggle.trigger('click')
    expect(wrapper.get<HTMLInputElement>('#jira-customfield_optional').element.value).toBe('Keep optional text')
    expect((assignee.element as HTMLInputElement).value).toBe('alice')
    await toggle.trigger('click')
    await wrapper.get('#jira-customfield_required').setValue('Required text')
    await openReview()
    await wrapper.get('.bug-btn--primary').trigger('click')
    await flushPromises()
    expect(createBug).toHaveBeenCalledWith(expect.objectContaining({
      assignee: 'alice', extraFields: { customfield_required: 'Required text', customfield_optional: 'Keep optional text' },
    }))
  })

  it('reveals a previously optional field when it is required in the next project', async () => {
    await loadFields()
    expect(wrapper.get('#jira-customfield_optional').isVisible()).toBe(false)
    vi.mocked(fetchJiraMeta).mockResolvedValueOnce(projectMeta('APP', [
      { ...textField('customfield_optional'), required: true },
    ]))
    await wrapper.get('[aria-label="Проект Jira"]').setValue('APP')
    await flushPromises()
    expect(wrapper.get('#jira-customfield_optional').isVisible()).toBe(true)
    expect(wrapper.find('[aria-controls="bug-issue-fields"]').exists()).toBe(false)
    await openReview()
    expect(wrapper.get('[role="alert"]').text()).toContain('customfield_optional')
    expect(previewBug).not.toHaveBeenCalled()
  })
})
