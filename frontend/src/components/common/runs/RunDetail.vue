<script setup lang="ts">
import { computed } from 'vue'

import TestResultList from '../results/TestResultList.vue'
import { fetchHistoryRunResults } from '../../../api/reports'
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
const loadedRun = computed(() => results.run.value)
const run = computed(() => loadedRun.value ?? props.summary)

const parsed = computed(() => (run.value ? parseReportName(run.value.name) : null))
const tone = computed(() => statusTone(run.value?.status))
const rateTone = computed(() => {
  const rate = run.value?.passRate ?? 0
  return rate < 70 ? 'failed' : rate < 90 ? 'broken' : 'ok'
})
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
</script>

<template>
  <section class="run" :aria-label="run ? `Прогон ${run.name}` : 'Прогон не выбран'">
    <template v-if="run">
      <header class="run-head">
        <div class="run-title-row">
          <div class="run-title">
            <h2>{{ run.name }}</h2>
            <span class="status-pill" :class="`status-pill--${tone}`">{{ run.status }}</span>
          </div>
          <RouterLink
            v-if="matchingReport"
            class="ghost-button"
            :to="{ name: 'report-by-id', params: { reportId: matchingReport.id } }"
          >
            Открыть Allure-отчёт
          </RouterLink>
        </div>

        <dl class="run-meta">
          <div v-if="parsed?.user">
            <dt>Автор</dt>
            <dd>{{ parsed.user }}</dd>
          </div>
          <div>
            <dt>Прогон</dt>
            <dd>{{ startedAt }}</dd>
          </div>
          <div v-if="run.duration">
            <dt>Длительность</dt>
            <dd>{{ formatShortDuration(run.duration) }}</dd>
          </div>
          <div>
            <dt>UUID</dt>
            <dd class="mono" :title="run.uuid">{{ run.uuid.slice(0, 8) }}</dd>
          </div>
          <div>
            <dt>Источник</dt>
            <dd>history.jsonl</dd>
          </div>
        </dl>

        <div class="run-stats">
          <div class="run-stat">
            <span>Pass rate</span>
            <strong :class="`rate--${rateTone}`">{{ run.passRate }}%</strong>
          </div>
          <div class="run-stat">
            <span>Всего</span>
            <strong>{{ run.total }}</strong>
          </div>
          <div class="run-stat">
            <span><i class="legend-dot legend-dot--failed"></i>Сбой</span>
            <strong>{{ run.failed }}</strong>
          </div>
          <div class="run-stat">
            <span><i class="legend-dot legend-dot--broken"></i>Сломано</span>
            <strong>{{ run.broken }}</strong>
          </div>
          <div class="run-stat">
            <span><i class="legend-dot legend-dot--passed"></i>Пройдено</span>
            <strong>{{ run.passed }}</strong>
          </div>
          <div v-if="run.other" class="run-stat">
            <span><i class="legend-dot legend-dot--other"></i>Прочее</span>
            <strong>{{ run.other }}</strong>
          </div>
        </div>
        <span v-if="run.total" class="stack-bar run-bar" aria-hidden="true">
          <span class="stack-bar-seg stack-bar-seg--passed" :style="{ width: shares.passed }"></span>
          <span class="stack-bar-seg stack-bar-seg--failed" :style="{ width: shares.failed }"></span>
          <span class="stack-bar-seg stack-bar-seg--broken" :style="{ width: shares.broken }"></span>
        </span>
      </header>

      <div class="run-results">
        <TestResultList
          v-model:status-filter="resultsStatus"
          :items="results.items.value"
          :total="results.total.value"
          :loading="results.loading.value"
          :error="results.error.value"
          :incidents-count="run.failed + run.broken"
          @retry="results.reload()"
        />
      </div>
    </template>

    <div v-else class="run-empty">
      <h2>Выберите прогон</h2>
      <p>
        Прогоны восстановлены из <code>history.jsonl</code> на сервере: здесь есть статусы и ошибки тестов, но нет
        полного Allure-отчёта.
      </p>
    </div>
  </section>
</template>

<style scoped src="../../../assets/style/components/runs/RunDetail.css"></style>
