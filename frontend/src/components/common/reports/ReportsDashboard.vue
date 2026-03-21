<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import type { HistoryRun, HistoryTestResult, Report } from '../../../types/reports'

type HistoryPoint = {
  key: string
  label: string
  total: number
  passed: number
  failed: number
  broken: number
  passRate: number
  reportId: string | null
}

type TagHealth = {
  tag: string
  total: number
  incidents: number
  healthyRate: number
}

type FailureSignature = {
  signature: string
  count: number
}

type UnstableTest = {
  key: string
  name: string
  totalRuns: number
  incidents: number
  stability: number
  lastStatus: string
}

type StabilityBucketKey = 'flaky' | 'alwaysFailed' | 'alwaysPassed' | 'incidents'

type StabilityDetailItem = {
  key: string
  name: string
  lastStatus: string
  incidents: number
  totalRuns: number
  history: HistoryTestResult[]
}

const props = defineProps<{
  reports: Report[]
  historyRuns: HistoryRun[]
  historyLoading: boolean
  selectedReportId: string | null
  formatDuration: (value: number | null | undefined) => string
  getReportTitle: (report: Report) => string | undefined
}>()

const route = useRoute()
const router = useRouter()
const activeTags = ref<string[]>([])
const activeSuite = ref('all')
const activeEnvironment = ref('all')
const activeSignature = ref('all')
const activeStabilityBucket = ref<StabilityBucketKey | null>(null)
const stabilitySearch = ref('')
const selectedTestKey = ref<string | null>(null)

function toTimestamp(value: string) {
  const timestamp = new Date(value).getTime()
  return Number.isFinite(timestamp) ? timestamp : 0
}

function openReport(id: string) {
  router.push({ name: 'report-by-id', params: { reportId: id } })
}

function parseQueryList(value: unknown) {
  if (typeof value !== 'string') return []
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function arraysEqual(left: string[], right: string[]) {
  if (left.length !== right.length) return false
  return left.every((item, index) => item === right[index])
}

function toggleTag(tag: string) {
  activeTags.value = activeTags.value.includes(tag)
    ? activeTags.value.filter((item) => item !== tag)
    : [...activeTags.value, tag].sort((left, right) => left.localeCompare(right))
}

function toggleSignature(signature: string) {
  activeSignature.value = activeSignature.value === signature ? 'all' : signature
}

function normalizeStatus(value: string | undefined) {
  return value?.trim().toLowerCase() ?? 'unknown'
}

function buildSignature(result: HistoryTestResult) {
  const base = result.message?.split('\n')[0]?.trim() || result.trace?.split('\n')[0]?.trim()
  if (!base) return 'Unknown failure'
  return base.length > 90 ? `${base.slice(0, 90)}…` : base
}

function buildRunLabel(run: HistoryRun) {
  if (run.name?.trim()) return run.name
  const date = new Date(run.timestamp)
  return Number.isNaN(date.getTime()) ? run.uuid : date.toLocaleString()
}

function resultMatchesFilters(result: HistoryTestResult) {
  const labels = result.labels ?? []
  const tagValues = labels.filter((label) => label.name === 'tag').map((label) => label.value)
  const suiteValue =
    labels.find((label) => label.name === 'suite')?.value ||
    labels.find((label) => label.name === 'parentSuite')?.value ||
    'unknown'
  const environmentValue = result.environment?.trim() || 'unknown'

  const tagMatches =
    activeTags.value.length === 0 || activeTags.value.some((tag) => tagValues.includes(tag))
  const suiteMatches = activeSuite.value === 'all' || suiteValue === activeSuite.value
  const environmentMatches =
    activeEnvironment.value === 'all' || environmentValue === activeEnvironment.value
  const signatureMatches =
    activeSignature.value === 'all' ||
    ((normalizeStatus(result.status) === 'failed' || normalizeStatus(result.status) === 'broken') &&
      buildSignature(result) === activeSignature.value)

  return tagMatches && suiteMatches && environmentMatches && signatureMatches
}

const reportMapByName = computed(() => {
  const map = new Map<string, string>()

  for (const report of props.reports) {
    const keys = [
      report.name,
      props.getReportTitle(report),
    ].filter((value): value is string => Boolean(value?.trim()))

    for (const key of keys) {
      map.set(key, report.id)
    }
  }

  return map
})

const filterOptions = computed(() => {
  const tags = new Set<string>()
  const suites = new Set<string>()
  const environments = new Set<string>()

  for (const run of props.historyRuns) {
    for (const result of Object.values(run.testResults ?? {})) {
      for (const label of result.labels ?? []) {
        if (label.name === 'tag' && label.value) tags.add(label.value)
        if ((label.name === 'suite' || label.name === 'parentSuite') && label.value) suites.add(label.value)
      }

      environments.add(result.environment?.trim() || 'unknown')
    }
  }

  return {
    tags: Array.from(tags).sort((left, right) => left.localeCompare(right)),
    suites: Array.from(suites).sort((left, right) => left.localeCompare(right)),
    environments: Array.from(environments).sort((left, right) => left.localeCompare(right)),
  }
})

watch(
  () => route.query,
  (query) => {
    const nextTags = parseQueryList(query.tags).sort((left, right) => left.localeCompare(right))
    const nextSuite = typeof query.suite === 'string' ? query.suite : 'all'
    const nextEnvironment = typeof query.environment === 'string' ? query.environment : 'all'
    const nextSignature = typeof query.signature === 'string' ? query.signature : 'all'

    if (!arraysEqual(activeTags.value, nextTags)) {
      activeTags.value = nextTags
    }
    activeSuite.value = nextSuite
    activeEnvironment.value = nextEnvironment
    activeSignature.value = nextSignature
  },
  { immediate: true },
)

watch([activeTags, activeSuite, activeEnvironment, activeSignature], () => {
  const nextQuery: Record<string, string> = {}

  if (activeTags.value.length) nextQuery.tags = activeTags.value.join(',')
  if (activeSuite.value !== 'all') nextQuery.suite = activeSuite.value
  if (activeEnvironment.value !== 'all') nextQuery.environment = activeEnvironment.value
  if (activeSignature.value !== 'all') nextQuery.signature = activeSignature.value

  const currentTags = parseQueryList(route.query.tags).sort((left, right) => left.localeCompare(right))
  const currentSuite = typeof route.query.suite === 'string' ? route.query.suite : 'all'
  const currentEnvironment =
    typeof route.query.environment === 'string' ? route.query.environment : 'all'
  const currentSignature = typeof route.query.signature === 'string' ? route.query.signature : 'all'

  if (
    arraysEqual(currentTags, activeTags.value) &&
    currentSuite === activeSuite.value &&
    currentEnvironment === activeEnvironment.value &&
    currentSignature === activeSignature.value
  ) {
    return
  }

  router.replace({ query: nextQuery })
})

const filteredHistoryRuns = computed(() => {
  return props.historyRuns
    .map((run) => {
      const filteredResults = Object.entries(run.testResults ?? {}).filter(([, result]) =>
        resultMatchesFilters(result),
      )

      return {
        ...run,
        testResults: Object.fromEntries(filteredResults),
      }
    })
    .filter((run) => Object.keys(run.testResults ?? {}).length > 0)
})

const historyResults = computed(() => {
  return filteredHistoryRuns.value.flatMap((run) => Object.values(run.testResults ?? {}))
})

const aggregateStats = computed(() => {
  return historyResults.value.reduce(
    (accumulator, result) => {
      const status = normalizeStatus(result.status)
      accumulator.total += 1

      if (status === 'passed') accumulator.passed += 1
      else if (status === 'failed') accumulator.failed += 1
      else if (status === 'broken') accumulator.broken += 1
      else if (status === 'flaky') accumulator.flaky += 1
      else accumulator.other += 1

      return accumulator
    },
    {
      total: 0,
      passed: 0,
      failed: 0,
      broken: 0,
      flaky: 0,
      other: 0,
    },
  )
})

const durationValues = computed(() =>
  historyResults.value
    .map((result) => result.duration)
    .filter((value): value is number => typeof value === 'number' && Number.isFinite(value))
    .sort((left, right) => left - right),
)

function percentile(values: number[], q: number) {
  if (!values.length) return null
  const index = Math.min(values.length - 1, Math.round((q / 100) * (values.length - 1)))
  return values[index] ?? null
}

const p95Duration = computed(() => percentile(durationValues.value, 95))
const passRate = computed(() =>
  aggregateStats.value.total ? Math.round((aggregateStats.value.passed / aggregateStats.value.total) * 100) : 0,
)
const incidentRate = computed(() => {
  const incidents = aggregateStats.value.failed + aggregateStats.value.broken
  return aggregateStats.value.total ? Math.round((incidents / aggregateStats.value.total) * 100) : 0
})

const historyByTest = computed(() => {
  const grouped = new Map<string, HistoryTestResult[]>()

  for (const result of historyResults.value) {
    const key = result.fullName || result.name || result.historyId || result.id
    if (!key) continue

    const bucket = grouped.get(key) ?? []
    bucket.push(result)
    grouped.set(key, bucket)
  }

  return grouped
})

const stabilitySummary = computed(() => {
  let flaky = 0
  let alwaysFailed = 0
  let alwaysPassed = 0

  for (const results of historyByTest.value.values()) {
    const statuses = new Set(results.map((result) => normalizeStatus(result.status)))
    const hasIncident = statuses.has('failed') || statuses.has('broken')
    const hasPassed = statuses.has('passed')

    if (hasIncident && hasPassed) flaky += 1
    if (hasIncident && !hasPassed) alwaysFailed += 1
    if (statuses.size === 1 && statuses.has('passed')) alwaysPassed += 1
  }

  return {
    uniqueTests: historyByTest.value.size,
    flaky,
    alwaysFailed,
    alwaysPassed,
  }
})

const stabilityDetails = computed(() => {
  const flaky: StabilityDetailItem[] = []
  const alwaysFailed: StabilityDetailItem[] = []
  const alwaysPassed: StabilityDetailItem[] = []
  const incidents: StabilityDetailItem[] = []

  for (const [key, results] of historyByTest.value.entries()) {
    const statuses = new Set(results.map((result) => normalizeStatus(result.status)))
    const hasIncident = statuses.has('failed') || statuses.has('broken')
    const hasPassed = statuses.has('passed')
    const latest = [...results].sort((left, right) => (right.stop ?? 0) - (left.stop ?? 0))[0]
    const item = {
      key,
      name: latest?.fullName || latest?.name || key,
      lastStatus: normalizeStatus(latest?.status),
      incidents: results.filter((result) => {
        const status = normalizeStatus(result.status)
        return status === 'failed' || status === 'broken'
      }).length,
      totalRuns: results.length,
      history: [...results].sort((left, right) => (right.stop ?? 0) - (left.stop ?? 0)),
    }

    if (hasIncident) incidents.push(item)
    if (hasIncident && hasPassed) flaky.push(item)
    if (hasIncident && !hasPassed) alwaysFailed.push(item)
    if (statuses.size === 1 && statuses.has('passed')) alwaysPassed.push(item)
  }

  const sorter = (left: StabilityDetailItem, right: StabilityDetailItem) =>
    right.incidents - left.incidents || left.name.localeCompare(right.name)

  return {
    flaky: flaky.sort(sorter),
    alwaysFailed: alwaysFailed.sort(sorter),
    alwaysPassed: alwaysPassed.sort(sorter),
    incidents: incidents.sort(sorter),
  }
})

const stabilityDialog = computed(() => {
  if (!activeStabilityBucket.value) return null

  const titles: Record<StabilityBucketKey, string> = {
    flaky: 'Flaky tests',
    alwaysFailed: 'Always failed',
    alwaysPassed: 'Always passed',
    incidents: 'Incidents',
  }

  return {
    title: titles[activeStabilityBucket.value],
    items: stabilityDetails.value[activeStabilityBucket.value],
  }
})

const filteredStabilityDialogItems = computed(() => {
  if (!stabilityDialog.value) return []

  const query = stabilitySearch.value.trim().toLowerCase()
  if (!query) return stabilityDialog.value.items

  return stabilityDialog.value.items.filter((item) => item.name.toLowerCase().includes(query))
})

const selectedTestDetails = computed(() => {
  if (!selectedTestKey.value) return null

  const history = historyByTest.value.get(selectedTestKey.value)
  if (!history?.length) return null

  const ordered = [...history].sort((left, right) => (right.stop ?? 0) - (left.stop ?? 0))
  const latest = ordered[0]
  const incidents = ordered.filter((result) => {
    const status = normalizeStatus(result.status)
    return status === 'failed' || status === 'broken'
  }).length

  return {
    name: latest?.fullName || latest?.name || selectedTestKey.value,
    lastStatus: normalizeStatus(latest?.status),
    totalRuns: ordered.length,
    incidents,
    history: ordered.slice(0, 8),
  }
})

watch(activeStabilityBucket, (value) => {
  if (!value) {
    stabilitySearch.value = ''
  }
})

watch(historyByTest, () => {
  if (selectedTestKey.value && !historyByTest.value.has(selectedTestKey.value)) {
    selectedTestKey.value = null
  }
})

const trendPoints = computed<HistoryPoint[]>(() => {
  return [...filteredHistoryRuns.value]
    .sort((left, right) => left.timestamp - right.timestamp)
    .slice(-8)
    .map((run) => {
      const results = Object.values(run.testResults ?? {})
      let passed = 0
      let failed = 0
      let broken = 0

      for (const result of results) {
        const status = normalizeStatus(result.status)
        if (status === 'passed') passed += 1
        else if (status === 'failed') failed += 1
        else if (status === 'broken') broken += 1
      }

      const total = results.length
      const reportId = reportMapByName.value.get(run.name) ?? null

      return {
        key: run.uuid,
        label: buildRunLabel(run),
        total,
        passed,
        failed,
        broken,
        passRate: total ? Math.round((passed / total) * 100) : 0,
        reportId,
      }
    })
})

const topUnstableTests = computed<UnstableTest[]>(() => {
  return Array.from(historyByTest.value.entries())
    .map(([key, results]) => {
      const incidents = results.filter((result) => {
        const status = normalizeStatus(result.status)
        return status === 'failed' || status === 'broken'
      }).length
      const totalRuns = results.length
      const stability = totalRuns ? Math.round(((totalRuns - incidents) / totalRuns) * 100) : 0
      const latest = [...results].sort((left, right) => (right.stop ?? 0) - (left.stop ?? 0))[0]

      return {
        key,
        name: latest?.fullName || latest?.name || key,
        totalRuns,
        incidents,
        stability,
        lastStatus: normalizeStatus(latest?.status),
      }
    })
    .filter((item) => item.totalRuns > 1 && item.incidents > 0)
    .sort((left, right) =>
      left.stability - right.stability ||
      right.incidents - left.incidents ||
      right.totalRuns - left.totalRuns,
    )
    .slice(0, 6)
})

const failureSignatures = computed<FailureSignature[]>(() => {
  const counts = new Map<string, number>()

  for (const result of historyResults.value) {
    const status = normalizeStatus(result.status)
    if (status !== 'failed' && status !== 'broken') continue

    const signature = buildSignature(result)
    counts.set(signature, (counts.get(signature) ?? 0) + 1)
  }

  return Array.from(counts.entries())
    .map(([signature, count]) => ({ signature, count }))
    .sort((left, right) => right.count - left.count)
    .slice(0, 5)
})

const tagHealth = computed<TagHealth[]>(() => {
  const counts = new Map<string, { total: number; incidents: number }>()

  for (const result of historyResults.value) {
    const tags = (result.labels ?? [])
      .filter((label) => label.name === 'tag' && label.value)
      .map((label) => label.value)

    const status = normalizeStatus(result.status)
    const hasIncident = status === 'failed' || status === 'broken'

    for (const tag of tags) {
      const bucket = counts.get(tag) ?? { total: 0, incidents: 0 }
      bucket.total += 1
      if (hasIncident) bucket.incidents += 1
      counts.set(tag, bucket)
    }
  }

  return Array.from(counts.entries())
    .map(([tag, value]) => ({
      tag,
      total: value.total,
      incidents: value.incidents,
      healthyRate: value.total ? Math.round(((value.total - value.incidents) / value.total) * 100) : 0,
    }))
    .sort((left, right) => right.incidents - left.incidents || left.healthyRate - right.healthyRate)
    .slice(0, 5)
})

const reportsWithStats = computed(() => props.reports.filter((report) => report.stats))

const selectedReport = computed(() => {
  if (!props.selectedReportId) return null
  return props.reports.find((report) => report.id === props.selectedReportId) ?? null
})

const topProblemRuns = computed(() => {
  return [...reportsWithStats.value]
    .map((report) => ({
      report,
      incidents: (report.stats?.failed ?? 0) + (report.stats?.broken ?? 0),
    }))
    .sort(
      (left, right) =>
        right.incidents - left.incidents ||
        toTimestamp(right.report.created_at) - toTimestamp(left.report.created_at),
    )
    .slice(0, 4)
})

const recentReports = computed(() => {
  const sorted = [...reportsWithStats.value].sort(
    (left, right) => toTimestamp(left.created_at) - toTimestamp(right.created_at),
  )

  return sorted.slice(-4).map((report) => {
    const total = report.stats?.total ?? 0
    const incidents = (report.stats?.failed ?? 0) + (report.stats?.broken ?? 0)
    const healthy = total > 0 ? Math.max(0, Math.round(((total - incidents) / total) * 100)) : 0

    return {
      id: report.id,
      label: props.getReportTitle(report) ?? report.id,
      healthy,
      incidents,
      total,
      selected: report.id === props.selectedReportId,
    }
  })
})

const ringStyle = computed(() => {
  const safePassRate = Math.max(0, Math.min(100, passRate.value))
  return {
    background: `conic-gradient(#22c55e 0 ${safePassRate}%, #ef4444 ${safePassRate}% ${safePassRate + Math.min(100 - safePassRate, incidentRate.value)}%, rgba(148, 163, 184, 0.18) ${safePassRate + Math.min(100 - safePassRate, incidentRate.value)}% 100%)`,
  }
})
</script>

<template>
  <section class="dashboard" aria-label="Dashboard">
    <div class="dashboard-hero">
      <div class="dashboard-copy">
        <span class="dashboard-eyebrow">Auto QA Observatory</span>
        <h2>История прогонов, стабильность и качество</h2>
        <p>
          Метрики строятся по `history.jsonl`: история тестов, нестабильность, сигнатуры падений
          и качество по тегам.
        </p>
      </div>

      <div class="dashboard-metrics">
        <article class="metric-card">
          <span class="metric-label">Runs</span>
          <strong class="metric-value">{{ filteredHistoryRuns.length }}</strong>
          <span class="metric-note">прогонов после фильтрации</span>
        </article>

        <article class="metric-card">
          <span class="metric-label">Unique tests</span>
          <strong class="metric-value">{{ stabilitySummary.uniqueTests }}</strong>
          <span class="metric-note">историй тест-кейсов</span>
        </article>

        <article class="metric-card metric-card--accent">
          <span class="metric-label">Pass rate</span>
          <strong class="metric-value">{{ passRate }}%</strong>
          <span class="metric-note">по всем историческим результатам</span>
        </article>

        <article class="metric-card">
          <span class="metric-label">P95 duration</span>
          <strong class="metric-value">{{ formatDuration(p95Duration) }}</strong>
          <span class="metric-note">длинный хвост времени выполнения</span>
        </article>
      </div>
      <div class="dashboard-filters">
        <div class="filters-heading">
          <span class="panel-kicker">Scope</span>
          <p>Фильтры ниже влияют на все метрики и виджеты на странице.</p>
        </div>

        <div class="filter-field filter-field--tags">
          <span>Tags</span>
          <div class="tag-filter-list">
          <button
            type="button"
            class="tag-filter-chip"
            :class="{ 'tag-filter-chip--active': activeTags.length === 0 }"
            @click="activeTags = []"
          >
            Все теги
          </button>
          <button
            v-for="tag in filterOptions.tags"
            :key="tag"
            type="button"
            class="tag-filter-chip"
            :class="{ 'tag-filter-chip--active': activeTags.includes(tag) }"
            @click="toggleTag(tag)"
          >
            {{ tag }}
          </button>
          </div>
        </div>

        <label class="filter-field">
          <span>Suite</span>
          <select v-model="activeSuite">
            <option value="all">Все suite</option>
            <option v-for="suite in filterOptions.suites" :key="suite" :value="suite">
              {{ suite }}
            </option>
          </select>
        </label>

        <label class="filter-field">
          <span>Environment</span>
          <select v-model="activeEnvironment">
            <option value="all">Все environment</option>
            <option v-for="environment in filterOptions.environments" :key="environment" :value="environment">
              {{ environment }}
            </option>
          </select>
        </label>

        <label class="filter-field">
          <span>Failure signature</span>
          <select v-model="activeSignature">
            <option value="all">Все сигнатуры</option>
            <option v-for="item in failureSignatures" :key="item.signature" :value="item.signature">
              {{ item.signature }}
            </option>
          </select>
        </label>

        <button
          v-if="activeTags.length || activeSuite !== 'all' || activeEnvironment !== 'all' || activeSignature !== 'all'"
          type="button"
          class="filter-reset"
          @click="
            activeTags = [];
            activeSuite = 'all';
            activeEnvironment = 'all';
            activeSignature = 'all'
          "
        >
          Сбросить
        </button>
      </div>
    </div>

    <div v-if="historyLoading" class="dashboard-loading">
      Загрузка history.jsonl…
    </div>

    <div v-else-if="!filteredHistoryRuns.length" class="dashboard-empty">
      <p>История прогонов пока не загружена.</p>
      <p>С текущими фильтрами данных нет. Сбрось фильтры или загрузи `history.jsonl`.</p>
    </div>

    <div v-else class="dashboard-grid">
      <article class="panel panel--span-4">
        <div class="panel-header">
          <div>
            <span class="panel-kicker">Health</span>
            <h3>Общая стабильность</h3>
          </div>
          <span class="panel-badge">risk {{ incidentRate }}%</span>
        </div>

        <div class="health-layout">
          <div class="health-ring" :style="ringStyle">
            <div class="health-ring-center">
              <strong>{{ passRate }}%</strong>
              <span>passed</span>
            </div>
          </div>

          <div class="health-legend">
            <div class="legend-row">
              <span class="legend-dot legend-dot--passed"></span>
              <span>Passed</span>
              <strong>{{ aggregateStats.passed }}</strong>
            </div>
            <div class="legend-row">
              <span class="legend-dot legend-dot--failed"></span>
              <span>Failed</span>
              <strong>{{ aggregateStats.failed }}</strong>
            </div>
            <div class="legend-row">
              <span class="legend-dot legend-dot--broken"></span>
              <span>Broken</span>
              <strong>{{ aggregateStats.broken }}</strong>
            </div>
            <div class="legend-row">
              <span class="legend-dot legend-dot--flaky"></span>
              <span>Flaky status</span>
              <strong>{{ aggregateStats.flaky }}</strong>
            </div>
          </div>
        </div>
      </article>

      <article class="panel panel--span-8">
        <div class="panel-header">
          <div>
            <span class="panel-kicker">Stability</span>
            <h3>Auto QA метрики</h3>
          </div>
        </div>

        <div class="qa-score-list">
          <button class="qa-score" type="button" @click="activeStabilityBucket = 'flaky'">
            <span>Flaky tests</span>
            <strong>{{ stabilitySummary.flaky }}</strong>
          </button>
          <button class="qa-score" type="button" @click="activeStabilityBucket = 'alwaysFailed'">
            <span>Always failed</span>
            <strong>{{ stabilitySummary.alwaysFailed }}</strong>
          </button>
          <button class="qa-score" type="button" @click="activeStabilityBucket = 'alwaysPassed'">
            <span>Always passed</span>
            <strong>{{ stabilitySummary.alwaysPassed }}</strong>
          </button>
          <button class="qa-score" type="button" @click="activeStabilityBucket = 'incidents'">
            <span>Incidents</span>
            <strong>{{ aggregateStats.failed + aggregateStats.broken }}</strong>
          </button>
        </div>
      </article>

      <article class="panel panel--span-12">
        <div class="panel-header">
          <div>
            <span class="panel-kicker">Trend</span>
            <h3>Последние прогоны</h3>
          </div>
        </div>

        <div class="run-trend-list">
          <div
            v-for="point in trendPoints"
            :key="point.key"
            class="run-trend-row"
          >
            <button
              v-if="point.reportId"
              type="button"
              class="run-trend-link"
              @click="openReport(point.reportId)"
            >
              {{ point.label }}
            </button>
            <span v-else class="run-trend-name">{{ point.label }}</span>
            <div class="run-trend-bar">
              <div
                class="run-trend-segment run-trend-segment--passed"
                :style="{ width: `${point.total ? Math.round((point.passed / point.total) * 100) : 0}%` }"
              ></div>
              <div
                class="run-trend-segment run-trend-segment--failed"
                :style="{ width: `${point.total ? Math.round((point.failed / point.total) * 100) : 0}%` }"
              ></div>
              <div
                class="run-trend-segment run-trend-segment--broken"
                :style="{ width: `${point.total ? Math.round((point.broken / point.total) * 100) : 0}%` }"
              ></div>
            </div>
            <span class="run-trend-meta">{{ point.total }} tests</span>
            <strong>{{ point.passRate }}%</strong>
          </div>
        </div>
      </article>

      <article class="panel panel--span-8">
        <div class="panel-header">
          <div>
            <span class="panel-kicker">Unstable</span>
            <h3>Самые нестабильные тесты</h3>
          </div>
        </div>

        <div class="unstable-list">
          <div
            v-for="item in topUnstableTests"
            :key="item.key"
            class="unstable-row"
          >
            <div class="unstable-copy">
              <div class="unstable-name">{{ item.name }}</div>
              <div class="unstable-meta">
                {{ item.incidents }} incidents · {{ item.totalRuns }} runs · last {{ item.lastStatus }}
              </div>
            </div>
            <div class="unstable-bar">
              <div class="unstable-bar-fill" :style="{ width: `${item.stability}%` }"></div>
            </div>
            <strong>{{ item.stability }}%</strong>
          </div>
        </div>
      </article>

      <article v-if="selectedTestDetails" class="panel panel--span-4">
        <div class="panel-header">
          <div>
            <span class="panel-kicker">Test Details</span>
            <h3>{{ selectedTestDetails.name }}</h3>
          </div>
        </div>

        <div class="test-detail-summary">
          <div class="test-detail-chip">
            <span>Last status</span>
            <strong>{{ selectedTestDetails.lastStatus }}</strong>
          </div>
          <div class="test-detail-chip">
            <span>Runs</span>
            <strong>{{ selectedTestDetails.totalRuns }}</strong>
          </div>
          <div class="test-detail-chip">
            <span>Incidents</span>
            <strong>{{ selectedTestDetails.incidents }}</strong>
          </div>
        </div>

        <div class="test-history-list">
          <div
            v-for="(result, index) in selectedTestDetails.history"
            :key="`${selectedTestDetails.name}-${index}-${result.start ?? 0}`"
            class="test-history-row"
          >
            <div>
              <div class="test-history-status" :class="`test-history-status--${normalizeStatus(result.status)}`">
                {{ normalizeStatus(result.status) }}
              </div>
              <div class="test-history-meta">
                {{ formatDuration(result.duration) }} · {{ result.environment || 'unknown' }}
              </div>
            </div>
            <div class="test-history-message">
              {{ result.message?.split('\n')[0] || 'Без сообщения' }}
            </div>
          </div>
        </div>
      </article>

      <article class="panel panel--span-4">
        <div class="panel-header">
          <div>
            <span class="panel-kicker">Failures</span>
            <h3>Failure signatures</h3>
          </div>
        </div>

        <div class="signature-list">
          <div
            v-for="item in failureSignatures"
            :key="item.signature"
            class="signature-row"
            :class="{ 'signature-row--active': activeSignature === item.signature }"
            @click="toggleSignature(item.signature)"
          >
            <span class="signature-text">{{ item.signature }}</span>
            <strong>{{ item.count }}</strong>
          </div>
        </div>
      </article>

      <article class="panel panel--span-4">
        <div class="panel-header">
          <div>
            <span class="panel-kicker">Tags</span>
            <h3>Health по тегам</h3>
          </div>
        </div>

        <div class="tag-list">
          <div
            v-for="item in tagHealth"
            :key="item.tag"
            class="tag-row"
            :class="{ 'tag-row--active': activeTags.includes(item.tag) }"
            @click="toggleTag(item.tag)"
          >
            <div class="tag-meta">
              <span class="tag-name">{{ item.tag }}</span>
              <span class="tag-caption">{{ item.total }} runs · {{ item.incidents }} incidents</span>
            </div>
            <div class="tag-bar">
              <div class="tag-bar-fill" :style="{ width: `${item.healthyRate}%` }"></div>
            </div>
            <strong>{{ item.healthyRate }}%</strong>
          </div>
        </div>
      </article>

      <article class="panel panel--span-8">
        <div class="panel-header">
          <div>
            <span class="panel-kicker">Reports</span>
            <h3>Последние отчеты</h3>
          </div>
        </div>

        <div class="trend-list">
          <button
            v-for="report in recentReports"
            :key="report.id"
            class="trend-row"
            type="button"
            :class="{ 'trend-row--active': report.selected }"
            @click="openReport(report.id)"
          >
            <div class="trend-meta">
              <span class="trend-name">{{ report.label }}</span>
              <span class="trend-caption">
                {{ report.total }} tests · {{ report.incidents }} incidents
              </span>
            </div>
            <div class="trend-bar">
              <div class="trend-bar-fill" :style="{ width: `${report.healthy}%` }"></div>
            </div>
            <strong>{{ report.healthy }}%</strong>
          </button>
        </div>
      </article>

      <article class="panel panel--span-4">
        <div class="panel-header">
          <div>
            <span class="panel-kicker">Attention</span>
            <h3>Проблемные прогоны</h3>
          </div>
        </div>

        <div class="problem-list">
          <button
            v-for="item in topProblemRuns"
            :key="item.report.id"
            class="problem-row"
            type="button"
            :class="{ 'problem-row--selected': item.report.id === selectedReport?.id }"
            @click="openReport(item.report.id)"
          >
            <div>
              <div class="problem-name">
                {{ getReportTitle(item.report) ?? item.report.id }}
              </div>
              <div class="problem-meta">
                Failed {{ item.report.stats?.failed ?? 0 }} · Broken {{ item.report.stats?.broken ?? 0 }}
              </div>
            </div>
            <strong>{{ item.incidents }}</strong>
          </button>
        </div>
      </article>
    </div>

    <div
      v-if="stabilityDialog"
      class="dashboard-modal-backdrop"
      @click.self="activeStabilityBucket = null"
    >
      <div class="dashboard-modal">
        <div class="dashboard-modal-header">
          <div>
            <span class="panel-kicker">Stability</span>
            <h3>{{ stabilityDialog.title }}</h3>
          </div>
          <button
            type="button"
            class="dashboard-modal-close"
            @click="activeStabilityBucket = null"
          >
            Закрыть
          </button>
        </div>

        <input
          v-model="stabilitySearch"
          type="search"
          class="dashboard-modal-search"
          placeholder="Найти тест по имени"
        />

        <div v-if="filteredStabilityDialogItems.length" class="dashboard-modal-list">
          <div
            v-for="item in filteredStabilityDialogItems"
            :key="item.key"
            class="dashboard-modal-row"
            @click="
              selectedTestKey = item.key;
              activeStabilityBucket = null
            "
          >
            <div class="dashboard-modal-row-main">
              <div class="dashboard-modal-row-title">{{ item.name }}</div>
              <div class="dashboard-modal-row-meta">
                last {{ item.lastStatus }} · {{ item.incidents }} incidents · {{ item.totalRuns }} runs
              </div>
            </div>
            <strong>{{ item.incidents }}</strong>
          </div>
        </div>
        <p v-else class="panel-empty">Для текущего набора фильтров список пуст.</p>
      </div>
    </div>
  </section>
</template>

<style scoped src="../../../assets/style/components/reports/ReportsDashboard.css"></style>
