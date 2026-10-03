<script setup lang="ts">
import { computed } from 'vue'

import DashboardTestDetailsPanel from '../reports/dashboard/DashboardTestDetailsPanel.vue'
import EntityToolbar, { type ToolbarCount, type ToolbarMeta } from '../layout/EntityToolbar.vue'
import TestResultList from '../results/TestResultList.vue'
import { fetchHistoryRunResults } from '../../../api/reports'
import { useTestDetailsDrawer } from '../../../composables/useTestDetailsDrawer'
import { useTestResults } from '../../../composables/useTestResults'
import { formatShortDuration, getReportTitle, parseReportName, statusTone } from '../../../utils/reports'
import type { HistoryRunSummary, Report } from '../../../types/reports'

const props = defineProps<{
  runId: string | null
  /** Summary from the list, shown instantly while results load. */
  summary: HistoryRunSummary | null
  reports: Report[]
}>()

const results = useTestResults(
  computed(() => props.runId),
  (id, status, signal) => fetchHistoryRunResults(id, status, signal),
)
const resultsStatus = results.statusFilter
const testDrawer = useTestDetailsDrawer()
const loadedRun = computed(() => results.run.value)
const run = computed(() => loadedRun.value ?? props.summary)

const parsed = computed(() => (run.value ? parseReportName(run.value.name) : null))
const tone = computed(() => statusTone(run.value?.status))
const startedAt = computed(() => {
  if (!run.value) return '-'
  const date = new Date(run.value.timestamp)
  return Number.isNaN(date.getTime())
    ? '-'
    : date.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
})
const shares = computed(() => {
  const r = run.value
  const share = (value: number) => `${r && r.total ? (value / r.total) * 100 : 0}%`
  return { passed: share(r?.passed ?? 0), failed: share(r?.failed ?? 0), broken: share(r?.broken ?? 0) }
})

// A ZIP report uploaded for the same run, if any (matched by exact name).
const matchingReport = computed(() =>
  run.value ? (props.reports.find((report) => getReportTitle(report) === run.value?.name) ?? null) : null,
)

const counts = computed<ToolbarCount[]>(() => {
  const r = run.value
  if (!r) return []
  return [
    { label: 'всего', value: r.total },
    { label: 'пройдено', value: r.passed, dot: 'passed' },
    { label: 'сбой', value: r.failed, dot: 'failed' },
    { label: 'сломано', value: r.broken, dot: 'broken' },
    { label: 'прочее', value: r.other, dot: 'other' },
  ]
})

const meta = computed<ToolbarMeta[]>(() => {
  const r = run.value
  if (!r) return []
  const items: ToolbarMeta[] = []
  if (parsed.value?.user) items.push({ label: 'Автор', value: parsed.value.user })
  items.push({ label: 'Прогон', value: startedAt.value })
  if (r.duration) items.push({ label: 'Длительность', value: formatShortDuration(r.duration) })
  items.push({ label: 'UUID', value: r.uuid.slice(0, 8), mono: true, title: r.uuid })
  items.push({ label: 'Источник', value: 'history.jsonl' })
  return items
})
</script>

<template>
  <section class="run" :aria-label="run ? `Прогон ${run.name}` : 'Прогон не выбран'">
    <template v-if="run">
      <EntityToolbar
        :title="run.name"
        :date-time="parsed ? `${parsed.date.slice(0, 5)} · ${parsed.time}` : null"
        :user="parsed?.user"
        :status="run.status"
        :tone="tone"
        :pass-rate="run.total ? run.passRate : null"
        :shares="run.total ? shares : null"
        :counts="counts"
        :meta="meta"
        :link="
          matchingReport
            ? { label: 'Открыть Allure-отчёт', to: { name: 'report-by-id', params: { reportId: matchingReport.id } } }
            : null
        "
        :reset-key="run.uuid"
      />

      <div class="run-results">
        <TestResultList
          v-model:status-filter="resultsStatus"
          :items="results.items.value"
          :total="results.total.value"
          :loading="results.loading.value"
          :error="results.error.value"
          :changes="results.changes.value"
          :opening-test-key="testDrawer.loadingKey.value"
          :incidents-count="run.failed + run.broken"
          @retry="results.reload()"
          @open-test="testDrawer.open($event)"
        />
        <p v-if="testDrawer.error.value" class="drawer-error" role="alert">{{ testDrawer.error.value }}</p>
      </div>
    </template>

    <div v-else class="run-empty">
      <h2>Выберите прогон</h2>
      <p>
        Прогоны восстановлены из <code>history.jsonl</code> на сервере: здесь есть статусы и ошибки тестов, но нет
        полного Allure-отчёта.
      </p>
    </div>

    <DashboardTestDetailsPanel
      v-if="testDrawer.details.value"
      :selected-test-details="testDrawer.details.value"
      :normalize-status="testDrawer.normalizeStatus"
      @close="testDrawer.close()"
    />
  </section>
</template>

<style scoped src="../../../assets/style/components/runs/RunDetail.css"></style>
