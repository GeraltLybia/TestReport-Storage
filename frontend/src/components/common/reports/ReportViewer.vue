<script setup lang="ts">
import { computed, ref } from 'vue'

import DashboardTestDetailsPanel from './dashboard/DashboardTestDetailsPanel.vue'
import EntityToolbar, {
  type ToolbarCount,
  type ToolbarMenuItem,
  type ToolbarMeta,
} from '../layout/EntityToolbar.vue'
import TestResultList from '../results/TestResultList.vue'
import { fetchReportResults } from '../../../api/reports'
import { useTestDetailsDrawer } from '../../../composables/useTestDetailsDrawer'
import { useTestResults } from '../../../composables/useTestResults'

import {
  formatDate,
  formatDuration,
  formatSize,
  getPassRate,
  getReportTitle,
  getReportTone,
  parseReportName,
} from '../../../utils/reports'
import type { Report } from '../../../types/reports'

const props = defineProps<{
  report: Report | null
  viewerSrc: string | null
}>()

const emit = defineEmits<{
  download: [id: string]
  delete: [id: string]
}>()

type ViewerTab = 'allure' | 'results'
const activeTab = ref<ViewerTab>('allure')

const reportId = computed(() => props.report?.id ?? null)
const results = useTestResults(
  reportId,
  (id, status, signal) => fetchReportResults(id, status, signal),
  computed(() => activeTab.value === 'results'),
)
const resultsStatus = results.statusFilter
const testDrawer = useTestDetailsDrawer()
const incidentsCount = computed(() => (props.report?.stats?.failed ?? 0) + (props.report?.stats?.broken ?? 0))
const title = computed(() => (props.report ? getReportTitle(props.report) : ''))
const parsed = computed(() => parseReportName(title.value))
const tone = computed(() => (props.report ? getReportTone(props.report) : 'other'))
const passRate = computed(() => (props.report ? getPassRate(props.report) : 0))

const stats = computed(() => {
  const s = props.report?.stats
  if (!s) return null
  const share = (value: number) => `${s.total ? (value / s.total) * 100 : 0}%`
  return {
    ...s,
    other: Math.max(0, s.total - s.passed - s.failed - s.broken - s.flaky),
    shares: { passed: share(s.passed), failed: share(s.failed), broken: share(s.broken), flaky: share(s.flaky) },
  }
})

const counts = computed<ToolbarCount[]>(() => {
  const s = stats.value
  if (!s) return []
  return [
    { label: 'всего', value: s.total },
    { label: 'пройдено', value: s.passed, dot: 'passed' },
    { label: 'сбой', value: s.failed, dot: 'failed' },
    { label: 'сломано', value: s.broken, dot: 'broken' },
    { label: 'нестабильно', value: s.flaky },
    { label: 'прочее', value: s.other, dot: 'other' },
  ]
})

const meta = computed<ToolbarMeta[]>(() => {
  const report = props.report
  if (!report) return []
  const items: ToolbarMeta[] = []
  if (parsed.value?.user) items.push({ label: 'Автор', value: parsed.value.user })
  if (parsed.value) items.push({ label: 'Прогон', value: `${parsed.value.date}, ${parsed.value.time}` })
  if (report.duration) items.push({ label: 'Длительность', value: formatDuration(report.duration) })
  items.push({ label: 'Загружен', value: formatDate(report.created_at) })
  items.push({ label: 'Размер', value: formatSize(report.size) })
  items.push({ label: 'ID', value: report.id.slice(0, 8), mono: true, title: report.id })
  return items
})

const menu = computed<ToolbarMenuItem[]>(() => {
  const report = props.report
  if (!report) return []
  return [
    { label: 'Скачать ZIP', icon: 'download', action: () => emit('download', report.id) },
    { label: 'Удалить отчёт', icon: 'delete', danger: true, action: () => emit('delete', report.id) },
  ]
})
</script>

<template>
  <section class="viewer" :aria-label="report ? `Отчёт ${title}` : 'Отчёт не выбран'">
    <template v-if="report">
      <EntityToolbar
        :title="title"
        :date-time="parsed ? `${parsed.date.slice(0, 5)} · ${parsed.time}` : null"
        :user="parsed?.user"
        :status="report.status || tone"
        :tone="tone"
        :pass-rate="stats ? passRate : null"
        :shares="stats?.total ? stats.shares : null"
        :counts="counts"
        :meta="meta"
        :link="viewerSrc ? { label: 'Открыть отдельно', href: viewerSrc } : null"
        :menu="menu"
        :reset-key="reportId"
      >
        <template #tabs>
          <div class="viewer-tabs" role="tablist" aria-label="Содержимое отчёта">
            <button type="button" role="tab" :aria-selected="activeTab === 'allure'" @click="activeTab = 'allure'">
              Allure-отчёт
            </button>
            <button type="button" role="tab" :aria-selected="activeTab === 'results'" @click="activeTab = 'results'">
              Результаты
              <span v-if="incidentsCount" class="viewer-tab-badge">{{ incidentsCount }}</span>
            </button>
          </div>
        </template>
      </EntityToolbar>

      <div v-if="activeTab === 'results'" class="viewer-results" role="tabpanel">
        <TestResultList
          v-model:status-filter="resultsStatus"
          :items="results.items.value"
          :total="results.total.value"
          :loading="results.loading.value"
          :error="results.error.value"
          :changes="results.changes.value"
          :opening-test-key="testDrawer.loadingKey.value"
          :incidents-count="incidentsCount"
          @retry="results.reload()"
          @open-test="testDrawer.open($event)"
        />
        <p v-if="testDrawer.error.value" class="drawer-error" role="alert">{{ testDrawer.error.value }}</p>
      </div>

      <div v-show="activeTab === 'allure'" class="viewer-frame-wrap" role="tabpanel">
        <iframe
          v-if="viewerSrc"
          :key="viewerSrc"
          :src="viewerSrc"
          :title="`Allure-отчёт ${title}`"
          sandbox="allow-scripts allow-popups"
          class="viewer-frame"
        />
        <p v-else class="viewer-placeholder">У этого отчёта нет index.html для просмотра.</p>
      </div>
    </template>

    <div v-else class="viewer-placeholder viewer-placeholder--empty">
      <svg viewBox="0 0 24 24" aria-hidden="true">
        <path d="M14 3v5h5" />
        <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
        <path d="M9 13h6M9 17h4" />
      </svg>
      <h2>Выберите отчёт</h2>
      <p>Список отчётов — слева.</p>
    </div>

    <DashboardTestDetailsPanel
      v-if="testDrawer.details.value"
      :selected-test-details="testDrawer.details.value"
      :normalize-status="testDrawer.normalizeStatus"
      @close="testDrawer.close()"
    />
  </section>
</template>

<style scoped src="../../../assets/style/components/reports/ReportViewer.css"></style>
