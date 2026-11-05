<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import JiraDynamicField from './JiraDynamicField.vue'
import { dynamicFields, hasFixedDefault, initialFieldValue, isEmptyField, mergeProjectFields } from '../../../utils/jiraFields'

import { commentBug, createBug, fetchBugDraft, fetchJiraMeta, previewBug } from '../../../api/jira'
import { fetchReportResults } from '../../../api/reports'
import {
  allStepIds,
  buildRows,
  callLabel,
  chosenCalls,
  chosenSteps,
  failureCall,
  foldedRepeats,
  initialExpanded,
  toggleGroup,
  type StepRow,
} from '../../../utils/jiraSteps'
import { describeChange, formatDate, formatShortDuration, formatSize, pluralRu, splitTestName, statusTone } from '../../../utils/reports'
import type {
  BugCommentResult,
  BugContent,
  BugDraft,
  BugIssueResult,
  BugIssueRequest,
  BugLogMode,
  BugStepGroup,
  JiraConfig,
  JiraIssueLink,
  JiraMeta,
} from '../../../types/jira'
import type { TestResultItem } from '../../../types/reports'

export type BugFiled =
  | { type: 'issue'; testId: string; logMode: BugLogMode; result: BugIssueResult }
  | { type: 'comment'; testId: string; result: BugCommentResult }

const props = defineProps<{
  reportId: string
  /** "Отчёт 28.09 · 05:00 · qa-alice" */
  context: string
  /** Test picked from its row; the report button opens the dialog without one. */
  initialTestId?: string | null
  links: Record<string, JiraIssueLink>
  config: JiraConfig | null
}>()

const emit = defineEmits<{
  close: []
  filed: [event: BugFiled]
}>()

const closeButton = ref<HTMLButtonElement | null>(null)

// ─── tests of the report ───
const tests = ref<TestResultItem[]>([])
const testsError = ref<string | null>(null)
const testsLoading = ref(true)
const testId = ref<string | null>(props.initialTestId ?? null)

async function loadTests() {
  testsLoading.value = true
  testsError.value = null
  try {
    const page = await fetchReportResults(props.reportId, 'incidents', new AbortController().signal)
    tests.value = page.items
    testId.value ??= page.items[0]?.id ?? null
  } catch (exception) {
    testsError.value = exception instanceof Error ? exception.message : 'Не удалось загрузить падения отчёта'
  } finally {
    testsLoading.value = false
  }
}

const testRows = computed(() =>
  tests.value.map((item) => {
    const technical = splitTestName(item.fullName || item.name)
    return {
      id: item.id,
      title: item.fullName && item.name !== item.fullName ? item.name : technical.method,
      error: item.message?.split('\n')[0] ?? '',
      duration: formatShortDuration(item.duration),
      tone: statusTone(item.status),
      badge: describeChange(item.change),
      jira: props.links[item.id] ?? null,
    }
  }),
)

// ─── draft and the form built from it ───
const draft = ref<BugDraft | null>(null)
const draftLoading = ref(false)
const draftError = ref<string | null>(null)
let draftController: AbortController | null = null

const selected = ref(new Set<string>())
const expanded = ref(new Set<string>())
const logMode = ref<BugLogMode>('calls')
const attachments = ref(new Set<string>())
const summary = ref('')
const expected = ref('')
const expectedInput = ref<HTMLTextAreaElement | null>(null)
const includeTrace = ref(true)
const priority = ref<string | null>(null)
const components = ref<string[]>([])
const labels = ref<string[]>([])
const labelInput = ref('')
const assignee = ref('')
const mode = ref<{ type: 'create' } | { type: 'comment'; key: string }>({ type: 'create' })
const duplicateDismissed = ref(false)
const tab = ref<'preview' | 'wiki'>('preview')
const expectedError = ref<string | null>(null)
const submitError = ref<string | null>(null)
const submitting = ref(false)
const review = ref<BugIssueRequest | null>(null)
const reviewDescription = ref<HTMLTextAreaElement | null>(null)

async function sendReviewedBug() {
  if (!review.value || submitting.value || !review.value.summary.trim() || !review.value.description?.trim()) return
  submitting.value = true
  submitError.value = null
  try {
    const payload = review.value
    const result = await createBug(payload)
    emit('filed', { type: 'issue', testId: payload.testId, logMode: payload.logMode, result })
  } catch (exception) {
    submitError.value = exception instanceof Error ? exception.message : 'Jira не ответила'
  } finally {
    submitting.value = false
  }
}

function backToForm() {
  if (submitting.value) return
  review.value = null
  submitError.value = null
  void nextTick(() => closeButton.value?.focus())
}

function resetForm(value: BugDraft) {
  selected.value = new Set(value.defaultSteps)
  expanded.value = initialExpanded(value.sections)
  logMode.value = 'calls'
  attachments.value = new Set(value.attachments.filter((item) => item.defaultSelected).map((item) => item.id))
  summary.value = value.suggested.summary
  expected.value = ''
  includeTrace.value = true
  components.value = []
  resetExtraFields()
  labels.value = [...value.suggested.labels]
  labelInput.value = ''
  assignee.value = value.suggested.assignee && value.suggested.assignee.found !== false ? value.suggested.assignee.name : ''
  mode.value = { type: 'create' }
  duplicateDismissed.value = false
  expectedError.value = null
  submitError.value = null
  applySystemDefaults()
}

async function loadDraft(id: string) {
  draftController?.abort()
  draftController = new AbortController()
  const { signal } = draftController
  draftLoading.value = true
  draftError.value = null
  try {
    const value = await fetchBugDraft(props.reportId, id, signal)
    if (signal.aborted) return
    draft.value = value
    resetForm(value)
  } catch (exception) {
    if (signal.aborted) return
    draft.value = null
    draftError.value = exception instanceof Error ? exception.message : 'Не удалось собрать черновик бага'
  } finally {
    if (!signal.aborted) draftLoading.value = false
  }
}

watch(testId, (id) => {
  if (id) void loadDraft(id)
})

// ─── Jira fields ───
const meta = ref<JiraMeta | null>(null)
const metaError = ref<string | null>(null)
const metaLoading = ref(false)
const projects = computed(() => props.config?.projectKeys ?? (props.config?.projectKey ? [props.config.projectKey] : []))
const selectedProject = ref(props.config?.projectKey ?? '')
watch(projects, values => {
  if (!values.includes(selectedProject.value)) selectedProject.value = values[0] ?? ''
}, { immediate: true })
let metaController: AbortController | null = null
const extraValues = ref<Record<string, unknown>>({})
const invalidFields = ref(new Set<string>())
const additionalFields = computed(() => dynamicFields(meta.value?.fieldDefinitions ?? []))
const fixedBuiltinFields = computed(() => (meta.value?.fieldDefinitions ?? []).filter(field =>
  ['priority', 'components', 'labels'].includes(field.id) && hasFixedDefault(field),
))
function fixedBuiltin(id: string) { return fixedBuiltinFields.value.some(field => field.id === id) }
function applyFixedSystemDefaults() {
  for (const field of fixedBuiltinFields.value) {
    const value = field.defaultValue
    const key = (item: unknown) => String(item && typeof item === 'object' ? (item as Record<string, unknown>).id : item)
    if (field.id === 'priority') priority.value = key(value)
    if (field.id === 'components') components.value = Array.isArray(value) ? value.map(key) : []
    if (field.id === 'labels') labels.value = Array.isArray(value) ? value.map(String) : []
  }
}
const showOptionalFields = ref(false)
const optionalFieldCount = computed(() =>
  additionalFields.value.filter(field => !field.required).length +
  ['priority', 'assignee', 'components', 'labels'].filter(id => meta.value?.fields.includes(id) && !requiredField(id)).length,
)
function hasField(id: string) { return !meta.value || meta.value.fields.includes(id) }
function requiredField(id: string) { return meta.value?.fieldDefinitions.find(f => f.id === id)?.required ?? false }
function applySystemDefaults() {
  const definitions = meta.value?.fieldDefinitions ?? []
  const defaults = (id: string) => definitions.find(f => f.id === id)?.defaultValue
  const componentDefaults = defaults('components')
  if (!components.value.length && Array.isArray(componentDefaults)) {
    components.value = componentDefaults.map(v => String(v.id))
  }
  const labelDefaults = defaults('labels')
  if (Array.isArray(labelDefaults)) labels.value = [...new Set([...labels.value, ...labelDefaults.map(String)])]
  const userDefault = defaults('assignee') as { name?: string } | undefined
  if (!assignee.value && userDefault?.name && userDefault.name !== '-1') assignee.value = userDefault.name
  applyFixedSystemDefaults()
}
function resetExtraFields() {
  extraValues.value = Object.fromEntries(additionalFields.value.map(f => [f.id, initialFieldValue(f)]))
  invalidFields.value = new Set()
}

async function loadMeta() {
  metaController?.abort()
  metaController = new AbortController()
  const { signal } = metaController
  const project = selectedProject.value
  metaLoading.value = true
  metaError.value = null
  try {
    const value = await fetchJiraMeta(project || undefined, signal)
    if (signal.aborted) return
    const previous = meta.value
    extraValues.value = mergeProjectFields(previous?.fieldDefinitions ?? [], value.fieldDefinitions, extraValues.value)
    if (!previous || !value.priorities.some(item => item.id === priority.value)) priority.value = value.defaultPriority
    components.value = components.value.filter(id => value.components.some(item => item.id === id))
    meta.value = value
    if (!previous) applySystemDefaults()
    else {
      // Defaults belong to the target project; shared user values take precedence.
      for (const id of ['components', 'labels', 'assignee']) {
        if (!previous.fields.includes(id) && value.fields.includes(id)) {
          const field = value.fieldDefinitions.find(field => field.id === id)
          if (id === 'components' && Array.isArray(field?.defaultValue)) components.value = field.defaultValue.map(item => String(item.id))
          if (id === 'labels' && Array.isArray(field?.defaultValue)) labels.value = [...new Set([...labels.value, ...field.defaultValue.map(String)])]
          if (id === 'assignee' && !assignee.value) {
            const name = (field?.defaultValue as { name?: string } | null)?.name
            if (name && name !== '-1') assignee.value = name
          }
        }
      }
    }
    applyFixedSystemDefaults()
    invalidFields.value = new Set()
    metaError.value = null
  } catch (exception) {
    if (signal.aborted) return
    metaError.value = exception instanceof Error ? exception.message : 'Jira недоступна'
  } finally {
    if (!signal.aborted) metaLoading.value = false
  }
}

watch(
  [() => props.config?.enabled, selectedProject],
  ([enabled]) => {
    if (enabled) void loadMeta()
  },
  { immediate: true },
)

const projectKey = computed(() => selectedProject.value || meta.value?.projectKey || '—')
const jiraHost = computed(() => {
  try {
    return props.config?.baseUrl ? new URL(props.config.baseUrl).host : null
  } catch {
    return props.config?.baseUrl ?? null
  }
})
const componentOptions = computed(() => (meta.value?.components ?? []).filter((item) => !components.value.includes(item.id)))
const componentName = (id: string) => meta.value?.components.find((item) => item.id === id)?.name ?? id

function addComponent(event: Event) {
  const select = event.target as HTMLSelectElement
  if (select.value) components.value = [...components.value, select.value]
  select.value = ''
}

function addLabel() {
  const value = labelInput.value.trim().replace(/\s+/g, '_')
  if (value && !labels.value.includes(value)) labels.value = [...labels.value, value]
  labelInput.value = ''
}

function removeLabel(label: string) {
  labels.value = labels.value.filter((item) => item !== label)
}

function onLabelKeydown(event: KeyboardEvent) {
  if (event.key === 'Enter' || event.key === ',') {
    event.preventDefault()
    addLabel()
  } else if (event.key === 'Backspace' && !labelInput.value && labels.value.length) {
    labels.value = labels.value.slice(0, -1)
  }
}

const assigneeHint = computed(() => {
  const suggestion = draft.value?.suggested.assignee
  if (!suggestion) return null
  if (assignee.value !== suggestion.name) return null
  if (suggestion.found === true) return `${suggestion.displayName} · автор теста`
  return 'Автор теста из отчёта'
})
const assigneeMissing = computed(() => {
  const suggestion = draft.value?.suggested.assignee
  return suggestion?.found === false ? `В Jira нет пользователя «${suggestion.name}» — исполнитель не назначен` : null
})

// ─── steps ───
const sections = computed(() => draft.value?.sections ?? [])
const rows = computed(() => buildRows(sections.value, selected.value, expanded.value))
const stepCount = computed(() => allStepIds(sections.value).length)
const stepsHint = computed(() => {
  const folded = foldedRepeats(sections.value)
  return `в задаче ${selected.value.size} из ${stepCount.value}${folded ? ` · свёрнуто повторов: ${folded}` : ''}`
})

function toggleStep(id: string) {
  const next = new Set(selected.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selected.value = next
}

function toggleRow(row: StepRow) {
  if (row.type === 'group') selected.value = toggleGroup(row.node as BugStepGroup, selected.value)
  else if (row.type === 'step') toggleStep(row.key)
}

function toggleExpanded(id: string) {
  const next = new Set(expanded.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  expanded.value = next
}

function pickFailurePath() {
  if (draft.value) selected.value = new Set(draft.value.defaultSteps)
}

function pickAll() {
  selected.value = new Set(allStepIds(sections.value))
}

function pickNone() {
  selected.value = new Set()
}

const STATUS_DOT: Record<string, string> = { failed: 'failed', broken: 'broken', skipped: 'skipped', passed: 'passed' }
const dot = (status: string) => STATUS_DOT[status] ?? 'skipped'

function rowSub(row: StepRow) {
  if (row.type === 'group') {
    const total = row.node.attempts.length
    return `${total} ${pluralRu(total, ['попытка', 'попытки', 'попыток'])} · в задаче ${row.selected || 'ни одной'}`
  }
  if (row.type !== 'step') return ''
  if (row.node.failureOrigin && row.node.message) return row.node.message.split('\n')[0]
  if (row.node.call) return callLabel(row.node.call)
  if (row.node.status === 'skipped') return 'не выполнялся'
  return ''
}

// ─── log and attachments ───
const logAttachments = computed(() => draft.value?.attachments.filter((item) => item.kind === 'log') ?? [])
const calls = computed(() => chosenCalls(sections.value, selected.value))
const brokenCall = computed(() => failureCall(sections.value))
const logHint = computed(() => {
  if (logMode.value === 'calls') {
    const parts = [`${calls.value.length} ${pluralRu(calls.value.length, ['запрос', 'запроса', 'запросов'])} выбранных шагов`]
    if (brokenCall.value) parts.push('тело запроса и ответ, на которых упал тест')
    return `В описание попадут ${parts.join(' и ')}.`
  }
  if (logMode.value === 'full') {
    const size = logAttachments.value.reduce((sum, item) => sum + (item.size ?? 0), 0)
    return logAttachments.value.length
      ? `В описание попадёт весь лог теста (${formatSize(size)}). Если не влезет в лимит Jira, начало обрежется — для длинных логов лучше файл.`
      : 'У теста нет лога.'
  }
  return 'Лога в описании не будет.'
})

function toggleAttachment(id: string) {
  const next = new Set(attachments.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  attachments.value = next
}

const chosenAttachments = computed(() => draft.value?.attachments.filter((item) => attachments.value.has(item.id)) ?? [])

// ─── duplicates ───
const duplicate = computed(() => {
  const value = draft.value
  if (!value) return null
  if (value.duplicates.exact) return { kind: 'exact' as const, link: value.duplicates.exact }
  const similar = value.duplicates.similar[0]
  if (similar) return { kind: 'similar' as const, link: similar }
  return null
})

function commentInto(key: string) {
  mode.value = { type: 'comment', key }
  expectedError.value = null
}

function createInstead() {
  mode.value = { type: 'create' }
  duplicateDismissed.value = true
}

// ─── description ───
const content = computed<BugContent | null>(() =>
  draft.value && testId.value
    ? {
        reportId: props.reportId,
        testId: testId.value,
        steps: [...selected.value],
        logMode: logMode.value,
        attachments: [...attachments.value],
        expected: expected.value,
        includeTrace: includeTrace.value,
      }
    : null,
)

// Numbered like the Jira list renders them: nested steps get 5.1, 5.2…
const previewSteps = computed(() =>
  chosenSteps(sections.value, selected.value).map((group) => {
    const counters: number[] = []
    return {
      ...group,
      steps: group.steps.map((item) => {
        counters.length = item.depth + 1
        counters[item.depth] = (counters[item.depth] ?? 0) + 1
        return { ...item, number: counters.map((value) => value ?? 1).join('.') }
      }),
    }
  }),
)
const previewHasSections = computed(
  () => previewSteps.value.length > 1 || (previewSteps.value[0] && previewSteps.value[0].section.id !== 'test'),
)
const runLine = computed(() => {
  const report = draft.value?.report
  if (!report) return ''
  const parts = [report.name]
  if (report.createdAt) parts.push(formatDate(report.createdAt))
  if (report.author && !report.name.includes(report.author)) parts.push(report.author)
  return parts.join(' · ')
})
const standLine = computed(() => {
  const stand = draft.value?.stand
  if (!stand) return null
  return stand.name ? `${stand.name} — ${stand.url}` : stand.url
})

const wikiText = ref('')
const wikiError = ref<string | null>(null)
let wikiTimer: ReturnType<typeof setTimeout> | null = null
let wikiController: AbortController | null = null

watch([tab, content], () => {
  if (tab.value !== 'wiki' || !content.value) return
  if (wikiTimer) clearTimeout(wikiTimer)
  const payload = content.value
  wikiTimer = setTimeout(async () => {
    wikiController?.abort()
    wikiController = new AbortController()
    const { signal } = wikiController
    try {
      const preview = await previewBug(payload, signal)
      if (signal.aborted) return
      wikiText.value = preview.description
      wikiError.value = null
    } catch (exception) {
      if (!signal.aborted) wikiError.value = exception instanceof Error ? exception.message : 'Не удалось собрать описание'
    }
  }, 250)
})

// ─── submit ───
const footerHint = computed(() => {
  if (props.config && !props.config.enabled) {
    return 'Jira не настроена: задайте JIRA_BASE_URL, JIRA_TOKEN и JIRA_PROJECT_KEY. Черновик и предпросмотр работают.'
  }
  const unsupported = meta.value?.unsupportedRequired ?? []
  if (unsupported.length) {
    return `Эти обязательные поля Jira пока не поддерживаются: ${unsupported.map((item) => item.name ?? item.id).join(', ')}.`
  }
  return 'Автор задачи — сервисный аккаунт Jira.'
})

const submitLabel = computed(() =>
  mode.value.type === 'comment'
    ? `Добавить комментарий в ${mode.value.key}`
    : meta.value?.projectKey || props.config?.projectKey
      ? `Создать баг в ${projectKey.value}`
      : 'Создать баг',
)

watch(expected, () => (expectedError.value = null))

async function submit() {
  if (!content.value || !testId.value || submitting.value) return
  submitError.value = null
  const currentTest = testId.value
  if (mode.value.type === 'create' && !expected.value.trim()) {
    expectedError.value = 'Опишите ожидаемый результат'
    tab.value = 'preview'
    await nextTick()
    expectedInput.value?.focus()
    expectedInput.value?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
    return
  }
  if (mode.value.type === 'create') {
    if (props.config?.enabled && (!meta.value || metaLoading.value || metaError.value || meta.value.projectKey !== selectedProject.value)) {
      submitError.value = 'Дождитесь загрузки полей Jira или повторите загрузку'
      return
    }
    const builtin: Record<string, unknown> = {
      summary: summary.value, priority: priority.value, components: components.value,
      labels: labels.value, assignee: assignee.value, environment: draft.value?.stand?.url,
    }
    const missing = (meta.value?.fieldDefinitions ?? []).filter(field => {
      if (['project', 'issuetype', 'reporter', 'attachment', 'description'].includes(field.id)) return false
      const value = field.id in builtin ? builtin[field.id] : extraValues.value[field.id]
      return field.required && !field.hasDefaultValue && isEmptyField(value)
    })
    invalidFields.value = new Set(missing.map(f => f.id))
    if (missing.length) {
      submitError.value = `Заполните обязательные поля: ${missing.map(f => f.name).join(', ')}`
      return
    }
    if (meta.value?.unsupportedRequired.length) {
      submitError.value = footerHint.value
      return
    }
  }
  submitting.value = true
  try {
    if (mode.value.type === 'comment') {
      const result = await commentBug(mode.value.key, content.value)
      emit('filed', { type: 'comment', testId: currentTest, result })
    } else {
      const payload: BugIssueRequest = {
        ...content.value,
        projectKey: projectKey.value,
        extraFields: extraValues.value,
        summary: summary.value,
        priority: priority.value,
        components: components.value,
        labels: labels.value,
        assignee: assignee.value.trim() || null,
      }
      const preview = await previewBug(payload)
      review.value = { ...payload, description: preview.description }
      await nextTick()
      reviewDescription.value?.focus()
    }
  } catch (exception) {
    submitError.value = exception instanceof Error ? exception.message : 'Jira не ответила'
  } finally {
    submitting.value = false
  }
}

// ─── dialog plumbing ───
function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && !submitting.value) {
    if (review.value) backToForm()
    else emit('close')
  }
}

let bodyOverflow = ''
onMounted(() => {
  document.addEventListener('keydown', onKeydown)
  bodyOverflow = document.body.style.overflow
  document.body.style.overflow = 'hidden'
  void loadTests()
  if (testId.value) void loadDraft(testId.value)
  void nextTick(() => closeButton.value?.focus())
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = bodyOverflow
  draftController?.abort()
  metaController?.abort()
  wikiController?.abort()
  if (wikiTimer) clearTimeout(wikiTimer)
})
</script>

<template>
  <Teleport to="body">
    <div class="bug-backdrop" @click.self="!submitting && (review ? backToForm() : emit('close'))">
      <section v-if="review" class="bug-dialog bug-dialog--review" role="dialog" aria-modal="true" aria-labelledby="bug-review-title">
        <header class="bug-header">
          <div class="bug-header-text">
            <h2 id="bug-review-title">Проверка перед отправкой в Jira</h2>
            <span class="bug-hint">Проект {{ projectKey }} · {{ context }}</span>
          </div>
        </header>
        <div class="bug-col bug-review-content">
          <label class="bug-field">
            <span class="bug-label">Заголовок</span>
            <input v-model="review.summary" class="bug-input" maxlength="255" :disabled="submitting" />
          </label>
          <label class="bug-field">
            <span class="bug-label">Описание в разметке Jira</span>
            <textarea ref="reviewDescription" v-model="review.description" class="bug-input bug-textarea bug-review-editor" rows="22" spellcheck="false" :disabled="submitting"></textarea>
          </label>
          <p class="bug-hint">Проверьте и отредактируйте итоговый текст. Выбранные вложения будут приложены к задаче.</p>
          <ul v-if="chosenAttachments.length" class="bug-env">
            <li v-for="item in chosenAttachments" :key="item.id">{{ item.name }}</li>
          </ul>
        </div>
        <footer class="bug-footer">
          <p v-if="submitError" class="bug-error bug-footer-error" role="alert">{{ submitError }}</p>
          <button type="button" class="bug-btn" :disabled="submitting" @click="backToForm">Назад к настройкам</button>
          <button type="button" class="bug-btn bug-btn--primary" :disabled="submitting || !review.summary.trim() || !review.description?.trim()" :aria-busy="submitting" @click="sendReviewedBug">
            {{ submitting ? 'Отправляем…' : submitLabel }}
          </button>
        </footer>
      </section>
      <section v-else class="bug-dialog" role="dialog" aria-modal="true" aria-labelledby="bug-dialog-title">
        <header class="bug-header">
          <span class="bug-header-icon" aria-hidden="true">
            <svg viewBox="0 0 24 24">
              <path d="M8 6a4 4 0 0 1 8 0" />
              <rect x="6" y="6" width="12" height="14" rx="6" />
              <path d="M12 10v10M3 13h3M18 13h3M4 7l3 2M20 7l-3 2M4 20l3-2M20 20l-3-2" />
            </svg>
          </span>
          <div class="bug-header-text">
            <h2 id="bug-dialog-title">Новый баг в Jira</h2>
            <span class="bug-hint">
              {{ context }}<template v-if="draft?.stand"> · {{ draft.stand.name || draft.stand.host }}</template>
            </span>
          </div>
          <button ref="closeButton" type="button" class="icon-button bug-close" aria-label="Закрыть" :disabled="submitting" @click="emit('close')">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" /></svg>
          </button>
        </header>

        <div class="bug-body" :inert="submitting">
          <!-- left: what goes into the bug -->
          <div class="bug-col bug-col--content">
            <section class="bug-sec">
              <div class="bug-sec-h">
                <span class="bug-num">1</span>
                <h3>Тест</h3>
                <span class="bug-hint">из падений этого отчёта</span>
              </div>
              <p v-if="testsLoading && !tests.length" class="bug-hint">Загрузка падений…</p>
              <p v-else-if="testsError" class="bug-error" role="alert">{{ testsError }}</p>
              <p v-else-if="!tests.length" class="bug-hint">В этом отчёте нет падений.</p>
              <div v-else class="bug-tests" role="radiogroup" aria-label="Тест для бага">
                <button
                  v-for="test in testRows"
                  :key="test.id"
                  type="button"
                  role="radio"
                  class="bug-test"
                  :class="{ 'is-selected': test.id === testId }"
                  :aria-checked="test.id === testId"
                  @click="testId = test.id"
                >
                  <span class="bug-radio" aria-hidden="true"></span>
                  <span class="bug-dot" :class="`bug-dot--${test.tone}`" aria-hidden="true"></span>
                  <span class="bug-test-main">
                    <span class="bug-test-title">
                      <span>{{ test.title }}</span>
                      <span v-if="test.badge" class="change-badge" :class="`change-badge--${test.badge.tone}`">{{ test.badge.label }}</span>
                      <span v-if="test.jira" class="jira-chip">
                        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2 2 12l10 10 10-10zm0 5 5 5-5 5-5-5z" /></svg>
                        {{ test.jira.key }}<template v-if="test.jira.status"> · {{ test.jira.status }}</template>
                      </span>
                    </span>
                    <span class="bug-mono bug-test-error" :class="`tone-${test.tone}`">{{ test.error }}</span>
                  </span>
                  <span class="bug-mono bug-muted">{{ test.duration }}</span>
                </button>
              </div>
            </section>

            <p v-if="draftError" class="bug-error" role="alert">
              {{ draftError }}
              <button v-if="testId" type="button" class="link-button" @click="loadDraft(testId)">Повторить</button>
            </p>

            <template v-if="draft">
              <section class="bug-sec" :aria-busy="draftLoading">
                <div class="bug-sec-h">
                  <span class="bug-num">2</span>
                  <h3>Шаги в задаче</h3>
                  <span class="bug-hint">{{ stepsHint }}</span>
                  <div class="bug-tools">
                    <button type="button" class="bug-tool" title="Шаги теста до падения, без подготовки и повторов" @click="pickFailurePath">
                      Путь до падения
                    </button>
                    <button type="button" class="bug-tool" @click="pickAll">Все</button>
                    <button type="button" class="bug-tool" @click="pickNone">Снять все</button>
                  </div>
                </div>
                <div v-if="rows.length" class="bug-steps">
                  <template v-for="row in rows" :key="row.key">
                    <div v-if="row.type === 'section'" class="bug-steps-section">{{ row.title }}</div>
                    <div
                      v-else
                      class="bug-step"
                      :class="{ 'is-on': row.state !== 'off', 'is-skipped': row.type === 'step' && row.node.status === 'skipped' }"
                      :style="{ '--depth': row.depth }"
                    >
                      <button
                        type="button"
                        role="checkbox"
                        class="bug-step-check"
                        :aria-checked="row.state === 'mixed' ? 'mixed' : row.state === 'on'"
                        @click="toggleRow(row)"
                      >
                        <span class="bug-cb" :class="`bug-cb--${row.state}`" aria-hidden="true">
                          <svg v-if="row.state === 'on'" viewBox="0 0 24 24"><path d="M5 12l5 5 9-10" /></svg>
                          <svg v-else-if="row.state === 'mixed'" viewBox="0 0 24 24"><path d="M6 12h12" /></svg>
                        </span>
                        <span class="bug-step-main">
                          <span class="bug-step-title" :class="{ 'is-failure': row.type === 'step' && row.node.failureOrigin, 'is-group': row.type === 'group' }">
                            <i class="bug-sdot" :class="`bug-dot--${dot(row.node.status)}`" aria-hidden="true"></i>
                            <span>{{ row.type === 'step' && row.attempt ? row.attempt : row.node.title }}</span>
                          </span>
                          <span v-if="rowSub(row)" class="bug-mono bug-step-sub" :class="{ 'tone-failed': row.type === 'step' && row.node.failureOrigin }">
                            {{ rowSub(row) }}
                          </span>
                        </span>
                      </button>
                      <button
                        v-if="row.type === 'group' || row.expandable"
                        type="button"
                        class="bug-expand"
                        :aria-expanded="row.expanded"
                        @click="toggleExpanded(row.key)"
                      >
                        <template v-if="row.type === 'group'">{{ row.expanded ? 'Свернуть' : `Показать ${row.node.attempts.length}` }}</template>
                        <template v-else>{{ row.expanded ? 'Скрыть шаги' : `Шаги · ${row.node.children.length}` }}</template>
                      </button>
                      <span class="bug-mono bug-muted bug-step-duration">{{ formatShortDuration(row.node.duration) }}</span>
                    </div>
                  </template>
                </div>
                <p v-else class="bug-hint">У теста нет шагов в отчёте.</p>
                <p class="bug-hint">
                  Повторы (ретраи, ожидания статуса) свёрнуты в одну строку — по умолчанию в задачу идёт только последняя
                  попытка. Подготовка и завершение по умолчанию выключены.
                </p>
              </section>

              <section class="bug-sec">
                <div class="bug-sec-h">
                  <span class="bug-num">3</span>
                  <h3>Лог и вложения</h3>
                  <span v-if="logAttachments.length" class="bug-hint">
                    {{ logAttachments.map((item) => item.name).join(', ') }} · {{ formatSize(logAttachments.reduce((sum, item) => sum + (item.size ?? 0), 0)) }}
                  </span>
                </div>
                <div class="bug-seg" role="group" aria-label="Лог в описании">
                  <button type="button" :aria-pressed="logMode === 'calls'" @click="logMode = 'calls'">Запросы шагов</button>
                  <button type="button" :aria-pressed="logMode === 'full'" @click="logMode = 'full'">Полный лог</button>
                  <button type="button" :aria-pressed="logMode === 'none'" @click="logMode = 'none'">Без лога</button>
                </div>
                <p class="bug-hint">{{ logHint }}</p>
                <div v-if="draft.attachments.length" class="bug-files">
                  <label v-for="item in draft.attachments" :key="item.id" class="bug-file">
                    <input type="checkbox" :checked="attachments.has(item.id)" @change="toggleAttachment(item.id)" />
                    <span class="bug-mono">{{ item.name }}</span>
                    <span class="bug-hint">{{ item.title }}<template v-if="item.size"> · {{ formatSize(item.size) }}</template></span>
                  </label>
                  <p class="bug-hint">Логи и дампы запросов уходят в Jira с замаскированными токенами и паролями.</p>
                </div>
              </section>
            </template>
            <p v-else-if="draftLoading" class="bug-hint">Собираем черновик…</p>
          </div>

          <!-- right: the Jira issue -->
          <div class="bug-col bug-col--issue">
            <section class="bug-sec">
              <div class="bug-sec-h">
                <span class="bug-num">4</span>
                <h3>Задача</h3>
                <span v-if="jiraHost" class="bug-hint">{{ jiraHost }}</span>
              </div>
              <div v-if="optionalFieldCount" class="bug-optional-fields">
                <button type="button" class="bug-tool" :aria-expanded="showOptionalFields" aria-controls="bug-issue-fields" @click="showOptionalFields = !showOptionalFields">
                  {{ showOptionalFields ? 'Скрыть необязательные поля' : `Показать необязательные поля (${optionalFieldCount})` }}
                </button>
                <span class="bug-hint">Заполненные значения сохраняются при скрытии.</span>
              </div>
              <div id="bug-issue-fields" class="bug-fields">
                <label class="bug-field">
                  <span class="bug-label">Проект</span>
                  <select v-if="projects.length > 1" v-model="selectedProject" class="bug-input" aria-label="Проект Jira" :disabled="mode.type === 'comment'">
                    <option v-for="project in projects" :key="project" :value="project">{{ project }}</option>
                  </select>
                  <div v-else class="bug-input bug-input--static"><b class="bug-mono">{{ projectKey }}</b></div>
                </label>
                <div class="bug-field">
                  <span class="bug-label">Тип</span>
                  <div class="bug-input bug-input--static">
                    <span class="bug-type-icon" aria-hidden="true"></span>{{ meta?.issueType.name ?? config?.issueType ?? 'Bug' }}
                  </div>
                </div>
                <label class="bug-field bug-field--wide">
                  <span class="bug-label">Заголовок *</span>
                  <input v-model="summary" class="bug-input" maxlength="255" :disabled="mode.type === 'comment'" />
                </label>
                <JiraDynamicField
                  v-for="field in fixedBuiltinFields"
                  v-show="field.required || showOptionalFields"
                  :key="field.id" :field="field" :disabled="mode.type === 'comment' || submitting"
                />
                <label v-if="hasField('priority') && !fixedBuiltin('priority')" v-show="showOptionalFields || requiredField('priority')" class="bug-field">
                  <span class="bug-label">Приоритет{{ requiredField('priority') ? ' *' : '' }}</span>
                  <select v-model="priority" class="bug-input" :disabled="!meta?.priorities.length || mode.type === 'comment'">
                    <option v-if="!meta?.priorities.length" :value="null">Нет данных из Jira</option>
                    <option v-for="item in meta?.priorities ?? []" :key="item.id" :value="item.id">{{ item.name }}</option>
                  </select>
                </label>
                <label v-if="hasField('assignee') && !fixedBuiltin('assignee')" v-show="showOptionalFields || requiredField('assignee')" class="bug-field">
                  <span class="bug-label">Исполнитель{{ requiredField('assignee') ? ' *' : '' }}</span>
                  <input id="bug-assignee" v-model="assignee" class="bug-input" placeholder="Не назначен" :disabled="mode.type === 'comment'" />
                  <span v-if="assigneeMissing" class="bug-field-note tone-broken">{{ assigneeMissing }}</span>
                  <span v-else-if="assigneeHint" class="bug-field-note">{{ assigneeHint }}</span>
                </label>
                <div v-if="hasField('components') && !fixedBuiltin('components')" v-show="showOptionalFields || requiredField('components')" class="bug-field">
                  <span class="bug-label">Компоненты{{ requiredField('components') ? ' *' : '' }}</span>
                  <div class="bug-input bug-input--chips">
                    <span v-for="id in components" :key="id" class="bug-chip">
                      {{ componentName(id) }}
                      <button type="button" :aria-label="`Убрать ${componentName(id)}`" @click="components = components.filter((item) => item !== id)">×</button>
                    </span>
                    <select
                      v-if="componentOptions.length && mode.type === 'create'"
                      class="bug-chip-select"
                      aria-label="Добавить компонент"
                      @change="addComponent"
                    >
                      <option value="">{{ components.length ? '+' : 'Добавить' }}</option>
                      <option v-for="item in componentOptions" :key="item.id" :value="item.id">{{ item.name }}</option>
                    </select>
                    <span v-else-if="!components.length" class="bug-muted">{{ meta ? 'Нет компонентов' : 'Нет данных из Jira' }}</span>
                  </div>
                </div>
                <div v-if="hasField('labels') && !fixedBuiltin('labels')" v-show="showOptionalFields || requiredField('labels')" class="bug-field">
                  <span class="bug-label">Метки{{ requiredField('labels') ? ' *' : '' }}</span>
                  <div class="bug-input bug-input--chips">
                    <span v-for="label in labels" :key="label" class="bug-chip">
                      {{ label }}
                      <button type="button" :aria-label="`Убрать метку ${label}`" @click="removeLabel(label)">×</button>
                    </span>
                    <input
                      v-model="labelInput"
                      class="bug-chip-input"
                      aria-label="Новая метка"
                      :placeholder="labels.length ? '' : 'Добавить метку'"
                      :disabled="mode.type === 'comment'"
                      @keydown="onLabelKeydown"
                      @blur="addLabel"
                    />
                  </div>
                </div>
                <JiraDynamicField
                  v-for="field in additionalFields"
                  v-show="field.required || showOptionalFields"
                  :key="field.id"
                  v-model="extraValues[field.id]"
                  :field="field" :disabled="mode.type === 'comment' || submitting"
                  :invalid="invalidFields.has(field.id) && isEmptyField(extraValues[field.id])"
                />
              </div>
              <p v-if="metaError" class="bug-field-note tone-failed">
                {{ metaError }} <button type="button" class="bug-tool" @click="loadMeta">Повторить загрузку полей</button>
              </p>
              <p v-if="metaLoading" class="bug-hint" role="status">Загрузка полей проекта {{ projectKey }}…</p>
            </section>

            <template v-if="draft">
              <div v-if="mode.type === 'comment'" class="bug-banner bug-banner--info">
                <div>
                  <b>Повторное падение уйдёт комментарием в {{ mode.key }}</b>
                  <span>Шаги, ошибка, запросы и выбранные вложения — без новой задачи.</span>
                  <span class="bug-banner-actions">
                    <button type="button" class="bug-tool" @click="createInstead">Создать новую задачу</button>
                  </span>
                </div>
              </div>
              <div v-else-if="duplicate && !duplicateDismissed" class="bug-banner">
                <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 9v4M12 17h.01M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z" /></svg>
                <div>
                  <b v-if="duplicate.kind === 'exact'">
                    Для этого теста уже есть задача
                    <a v-if="duplicate.link.url" :href="duplicate.link.url" target="_blank" rel="noopener">{{ duplicate.link.key }}</a>
                    <template v-else>{{ duplicate.link.key }}</template><template v-if="duplicate.link.status"> · {{ duplicate.link.status }}</template>
                  </b>
                  <b v-else>
                    Похоже на
                    <a v-if="duplicate.link.url" :href="duplicate.link.url" target="_blank" rel="noopener">{{ duplicate.link.key }}</a>
                    <template v-else>{{ duplicate.link.key }}</template><template v-if="duplicate.link.status"> · {{ duplicate.link.status }}</template>
                  </b>
                  <span>
                    «{{ draft.test.signature }}» —
                    <template v-if="duplicate.kind === 'exact'">та же ошибка<template v-if="duplicate.link.createdAt">, заведена {{ formatDate(duplicate.link.createdAt) }}</template>.</template>
                    <template v-else>такая же ошибка в тесте «{{ duplicate.link.testKey }}».</template>
                    Можно добавить в неё комментарий с новым прогоном вместо дубля.
                  </span>
                  <span class="bug-banner-actions">
                    <button type="button" class="bug-tool bug-tool--strong" @click="commentInto(duplicate.link.key)">
                      Комментарий в {{ duplicate.link.key }}
                    </button>
                    <button type="button" class="bug-tool" @click="duplicateDismissed = true">Всё равно создать новую</button>
                  </span>
                </div>
              </div>
              <p v-else-if="!duplicate" class="bug-hint">Задач с такой ошибкой ещё не заводили.</p>

              <div class="bug-description">
                <div class="bug-description-bar">
                  <b>{{ mode.type === 'comment' ? 'Комментарий' : 'Описание' }}</b>
                  <div class="bug-seg">
                    <button type="button" :aria-pressed="tab === 'preview'" @click="tab = 'preview'">Предпросмотр</button>
                    <button type="button" :aria-pressed="tab === 'wiki'" @click="tab = 'wiki'">Разметка Jira</button>
                  </div>
                </div>
                <div v-if="tab === 'preview'" class="bug-preview">
                  <h4>Шаги воспроизведения</h4>
                  <template v-for="group in previewSteps" :key="group.section.id">
                    <p v-if="previewHasSections" class="bug-preview-section">{{ group.section.title }}</p>
                    <ol class="bug-preview-steps">
                      <li
                        v-for="item in group.steps"
                        :key="item.id"
                        :class="{ 'is-failure': item.failure, 'is-skipped': item.skipped }"
                        :style="{ '--depth': item.depth }"
                      >
                        <span class="bug-preview-num">{{ item.number }}.</span>
                        <span>
                          {{ item.label }}
                          <span v-if="item.sub" class="bug-mono bug-preview-sub">{{ item.sub }}</span>
                        </span>
                      </li>
                    </ol>
                  </template>
                  <p v-if="!previewSteps.length" class="bug-hint">Шаги не выбраны.</p>

                  <h4>Фактический результат</h4>
                  <pre class="bug-code bug-code--error">{{ draft.error.message || 'Тест упал без сообщения об ошибке' }}</pre>
                  <label v-if="draft.error.trace" class="bug-inline-check">
                    <input v-model="includeTrace" type="checkbox" /> Трассировка (последние 40 строк)
                  </label>

                  <template v-if="mode.type === 'create'">
                    <h4><label for="bug-expected">Ожидаемый результат</label></h4>
                    <textarea
                      id="bug-expected"
                      ref="expectedInput"
                      v-model="expected"
                      class="bug-input bug-textarea"
                      rows="2"
                      placeholder="Заказ в статусе «paid» отменяется: PATCH /status → 200"
                      :aria-invalid="!!expectedError"
                      :aria-describedby="expectedError ? 'bug-expected-error' : undefined"
                    ></textarea>
                    <span v-if="expectedError" id="bug-expected-error" class="bug-field-note tone-failed">{{ expectedError }}</span>
                  </template>

                  <template v-if="logMode === 'calls' && (calls.length || brokenCall)">
                    <h4>Запросы</h4>
                    <pre v-if="calls.length" class="bug-code">{{ calls.join('\n') }}</pre>
                    <p v-if="brokenCall" class="bug-hint">
                      Тест упал на <span class="bug-mono">{{ callLabel(brokenCall) }}</span> — тело запроса и ответ будут в описании.
                    </p>
                  </template>
                  <template v-else-if="logMode === 'full' && logAttachments.length">
                    <h4>Лог</h4>
                    <p class="bug-hint">Весь лог теста, секреты замаскированы.</p>
                  </template>

                  <h4>Окружение и ссылки</h4>
                  <ul class="bug-env">
                    <li v-if="standLine">Стенд: {{ standLine }}</li>
                    <li>{{ runLine }}</li>
                    <li v-if="draft.test.parameters.length" class="bug-mono">
                      {{ draft.test.parameters.map((item) => `${item.name}=${item.value}`).join(', ') }}
                    </li>
                    <li v-if="draft.links.report"><a :href="draft.links.report" target="_blank" rel="noopener">Отчёт в TestReport Storage ↗</a></li>
                    <li v-if="draft.links.allure"><a :href="draft.links.allure" target="_blank" rel="noopener">Тест в Allure-отчёте ↗</a></li>
                    <li v-for="item in chosenAttachments" :key="item.id" class="bug-env-file">
                      <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m21 12-8.5 8.5a5 5 0 0 1-7-7L14 5a3.3 3.3 0 0 1 4.7 4.7L10 18.4a1.7 1.7 0 0 1-2.4-2.4L15.5 8" /></svg>
                      {{ item.name }}
                    </li>
                  </ul>
                </div>
                <template v-else>
                  <p v-if="wikiError" class="bug-error" role="alert">{{ wikiError }}</p>
                  <pre v-else class="bug-code bug-code--wiki">{{ wikiText || 'Собираем разметку…' }}</pre>
                </template>
              </div>
            </template>
          </div>
        </div>

        <footer class="bug-footer">
          <span class="bug-hint bug-footer-hint">{{ footerHint }}</span>
          <p v-if="submitError" class="bug-error bug-footer-error" role="alert">{{ submitError }}</p>
          <button type="button" class="bug-btn" :disabled="submitting" @click="emit('close')">Отмена</button>
          <button
            type="button"
            class="bug-btn bug-btn--primary"
            :disabled="!draft || submitting || (mode.type === 'create' && (metaLoading || !!metaError))"
            :aria-busy="submitting"
            @click="submit"
          >
            {{ submitting ? (mode.type === 'create' ? 'Собираем задачу…' : 'Отправляем…') : (mode.type === 'create' ? 'Проверить перед отправкой' : submitLabel) }}
          </button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<style scoped src="../../../assets/style/components/jira/JiraFields.css"></style>
<style scoped src="../../../assets/style/components/jira/BugCreateDialog.css"></style>
