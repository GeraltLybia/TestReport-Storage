<script setup lang="ts">
import { computed, ref } from 'vue'

import DashboardTestDetailsPanel from './dashboard/DashboardTestDetailsPanel.vue'
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
const rateTone = computed(() => (passRate.value < 70 ? 'failed' : passRate.value < 90 ? 'broken' : 'ok'))

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
</script>

<template>
  <section class="viewer" :aria-label="report ? `Отчёт ${title}` : 'Отчёт не выбран'">
    <template v-if="report">
      <header class="viewer-head">
        <div class="viewer-title-row">
          <div class="viewer-title">
            <h2>{{ title }}</h2>
            <span class="status-pill" :class="`status-pill--${tone}`">{{ report.status || tone }}</span>
          </div>
          <div class="viewer-actions">
            <a v-if="viewerSrc" class="ghost-button" :href="viewerSrc" target="_blank" rel="noopener">
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M14 4h6v6M20 4l-9 9" />
                <path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" />
              </svg>
              Открыть отдельно
            </a>
            <button type="button" class="icon-button" aria-label="Скачать ZIP" title="Скачать ZIP" @click="emit('download', report.id)">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4v12M7 11l5 5 5-5M4 20h16" /></svg>
            </button>
            <button
              type="button"
              class="icon-button icon-button--danger"
              aria-label="Удалить отчёт"
              title="Удалить отчёт"
              @click="emit('delete', report.id)"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" /></svg>
            </button>
          </div>
        </div>

        <dl class="viewer-meta">
          <div v-if="parsed?.user">
            <dt>Автор</dt>
            <dd>{{ parsed.user }}</dd>
          </div>
          <div v-if="parsed">
            <dt>Прогон</dt>
            <dd>{{ parsed.date }}, {{ parsed.time }}</dd>
          </div>
          <div>
            <dt>Загружен</dt>
            <dd>{{ formatDate(report.created_at) }}</dd>
          </div>
          <div v-if="report.duration">
            <dt>Длительность</dt>
            <dd>{{ formatDuration(report.duration) }}</dd>
          </div>
          <div>
            <dt>Размер</dt>
            <dd>{{ formatSize(report.size) }}</dd>
          </div>
          <div>
            <dt>ID</dt>
            <dd class="mono" :title="report.id">{{ report.id.slice(0, 8) }}</dd>
          </div>
        </dl>

        <template v-if="stats">
          <div class="viewer-stats">
            <div class="viewer-stat">
              <span>Pass rate</span>
              <strong :class="`rate--${rateTone}`">{{ passRate }}%</strong>
            </div>
            <div class="viewer-stat">
              <span>Всего</span>
              <strong>{{ stats.total }}</strong>
            </div>
            <div class="viewer-stat">
              <span><i class="legend-dot legend-dot--failed"></i>Сбой</span>
              <strong>{{ stats.failed }}</strong>
            </div>
            <div class="viewer-stat">
              <span><i class="legend-dot legend-dot--broken"></i>Сломано</span>
              <strong>{{ stats.broken }}</strong>
            </div>
            <div class="viewer-stat">
              <span><i class="legend-dot legend-dot--passed"></i>Пройдено</span>
              <strong>{{ stats.passed }}</strong>
            </div>
            <div class="viewer-stat">
              <span>Нестабильно</span>
              <strong>{{ stats.flaky }}</strong>
            </div>
            <div v-if="stats.other" class="viewer-stat">
              <span><i class="legend-dot legend-dot--other"></i>Прочее</span>
              <strong>{{ stats.other }}</strong>
            </div>
          </div>
          <span v-if="stats.total" class="stack-bar viewer-bar" aria-hidden="true">
            <span class="stack-bar-seg stack-bar-seg--passed" :style="{ width: stats.shares.passed }"></span>
            <span class="stack-bar-seg stack-bar-seg--failed" :style="{ width: stats.shares.failed }"></span>
            <span class="stack-bar-seg stack-bar-seg--broken" :style="{ width: stats.shares.broken }"></span>
          </span>
        </template>
      </header>

      <div class="viewer-tabs" role="tablist" aria-label="Содержимое отчёта">
        <button
          type="button"
          role="tab"
          :aria-selected="activeTab === 'allure'"
          @click="activeTab = 'allure'"
        >
          Allure-отчёт
        </button>
        <button
          type="button"
          role="tab"
          :aria-selected="activeTab === 'results'"
          @click="activeTab = 'results'"
        >
          Результаты тестов
          <span v-if="incidentsCount" class="viewer-tab-badge">{{ incidentsCount }}</span>
        </button>
      </div>

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
