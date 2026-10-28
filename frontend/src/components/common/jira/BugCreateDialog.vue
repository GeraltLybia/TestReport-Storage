<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

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

function resetForm(value: BugDraft) {
  selected.value = new Set(value.defaultSteps)
  expanded.value = initialExpanded(value.sections)
  logMode.value = 'calls'
  attachments.value = new Set(value.attachments.filter((item) => item.defaultSelected).map((item) => item.id))
  summary.value = value.suggested.summary
  expected.value = ''
  includeTrace.value = true
  components.value = []
  labels.value = [...value.suggested.labels]
  labelInput.value = ''
  assignee.value = value.suggested.assignee && value.suggested.assignee.found !== false ? value.suggested.assignee.name : ''
  mode.value = { type: 'create' }
  duplicateDismissed.value = false
  expectedError.value = null
  submitError.value = null
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

async function loadMeta() {
  try {
    meta.value = await fetchJiraMeta()
    priority.value ??= meta.value.defaultPriority
  } catch (exception) {
    metaError.value = exception instanceof Error ? exception.message : 'Jira недоступна'
  }
}

watch(
  () => props.config?.enabled,
  (enabled) => {
    if (enabled && !meta.value) void loadMeta()
  },
  { immediate: true },
)

const projectKey = computed(() => meta.value?.projectKey ?? props.config?.projectKey ?? '—')
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
    return `В проекте есть обязательные поля, которых нет в форме: ${unsupported.map((item) => item.name ?? item.id).join(', ')}. Jira может отклонить задачу.`
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
    return
  }
  submitting.value = true
  try {
    if (mode.value.type === 'comment') {
      const result = await commentBug(mode.value.key, content.value)
      emit('filed', { type: 'comment', testId: currentTest, result })
    } else {
      const result = await createBug({
        ...content.value,
        summary: summary.value,
        priority: priority.value,
        components: components.value,
        labels: labels.value,
        assignee: assignee.value.trim() || null,
      })
      emit('filed', { type: 'issue', testId: currentTest, logMode: logMode.value, result })
    }
  } catch (exception) {
    submitError.value = exception instanceof Error ? exception.message : 'Jira не ответила'
  } finally {
    submitting.value = false
  }
}

// ─── dialog plumbing ───
function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && !submitting.value) emit('close')
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
  wikiController?.abort()
  if (wikiTimer) clearTimeout(wikiTimer)
})
</script>

<template>
  <Teleport to="body">
    <div class="bug-backdrop" @click.self="!submitting && emit('close')">
      <section class="bug-dialog" role="dialog" aria-modal="true" aria-labelledby="bug-dialog-title">
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
          <button ref="closeButton" type="button" class="icon-button bug-close" aria-label="Закрыть" @click="emit('close')">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6 6 18" /></svg>
          </button>
        </header>

        <div class="bug-body">
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
              <div class="bug-fields">
                <div class="bug-field">
                  <span class="bug-label">Проект</span>
                  <div class="bug-input bug-input--static"><b class="bug-mono">{{ projectKey }}</b></div>
                </div>
                <div class="bug-field">
                  <span class="bug-label">Тип</span>
                  <div class="bug-input bug-input--static">
                    <span class="bug-type-icon" aria-hidden="true"></span>{{ meta?.issueType.name ?? config?.issueType ?? 'Bug' }}
                  </div>
                </div>
                <label class="bug-field bug-field--wide">
                  <span class="bug-label">Заголовок</span>
                  <input v-model="summary" class="bug-input" maxlength="255" :disabled="mode.type === 'comment'" />
                </label>
                <label class="bug-field">
                  <span class="bug-label">Приоритет</span>
                  <select v-model="priority" class="bug-input" :disabled="!meta?.priorities.length || mode.type === 'comment'">
                    <option v-if="!meta?.priorities.length" :value="null">Нет данных из Jira</option>
                    <option v-for="item in meta?.priorities ?? []" :key="item.id" :value="item.id">{{ item.name }}</option>
                  </select>
                </label>
                <label class="bug-field">
                  <span class="bug-label">Исполнитель</span>
                  <input v-model="assignee" class="bug-input" placeholder="Не назначен" :disabled="mode.type === 'comment'" />
                  <span v-if="assigneeMissing" class="bug-field-note tone-broken">{{ assigneeMissing }}</span>
                  <span v-else-if="assigneeHint" class="bug-field-note">{{ assigneeHint }}</span>
                </label>
                <div class="bug-field">
                  <span class="bug-label">Компоненты</span>
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
                <div class="bug-field">
                  <span class="bug-label">Метки</span>
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
              </div>
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
            :disabled="!draft || submitting"
            :aria-busy="submitting"
            @click="submit"
          >
            {{ submitting ? 'Отправляем…' : submitLabel }}
          </button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<style scoped src="../../../assets/style/components/jira/BugCreateDialog.css"></style>
