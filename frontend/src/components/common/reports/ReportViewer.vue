<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

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
  pluralRu,
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

type ViewerMenu = 'info' | 'more'
const openMenu = ref<ViewerMenu | null>(null)
const toolbar = ref<HTMLElement | null>(null)

function toggleMenu(menu: ViewerMenu) {
  openMenu.value = openMenu.value === menu ? null : menu
}

function runAction(action: 'download' | 'delete') {
  openMenu.value = null
  if (!props.report) return
  if (action === 'download') emit('download', props.report.id)
  else emit('delete', props.report.id)
}

function onDocumentClick(event: MouseEvent) {
  if (openMenu.value && toolbar.value && !toolbar.value.contains(event.target as Node)) openMenu.value = null
}

function closeMenu() {
  openMenu.value = null
}

function onDocumentKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') openMenu.value = null
}

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
  document.addEventListener('keydown', onDocumentKeydown)
  // Clicks inside the Allure iframe never reach the document; the window loses focus instead.
  window.addEventListener('blur', closeMenu)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick)
  document.removeEventListener('keydown', onDocumentKeydown)
  window.removeEventListener('blur', closeMenu)
})

watch(reportId, () => {
  openMenu.value = null
})

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
      <header ref="toolbar" class="viewer-toolbar">
        <div class="viewer-tabs" role="tablist" aria-label="Содержимое отчёта">
          <button type="button" role="tab" :aria-selected="activeTab === 'allure'" @click="activeTab = 'allure'">
            Allure-отчёт
          </button>
          <button type="button" role="tab" :aria-selected="activeTab === 'results'" @click="activeTab = 'results'">
            Результаты
            <span v-if="incidentsCount" class="viewer-tab-badge">{{ incidentsCount }}</span>
          </button>
        </div>

        <span class="viewer-divider" aria-hidden="true"></span>

        <div class="viewer-title" :title="title">
          <h2 v-if="parsed" class="viewer-title-date">{{ parsed.date.slice(0, 5) }} · {{ parsed.time }}</h2>
          <h2 v-else class="viewer-title-text">{{ title }}</h2>
          <span v-if="parsed?.user" class="viewer-title-user">{{ parsed.user }}</span>
          <span class="status-pill" :class="`status-pill--${tone}`">{{ report.status || tone }}</span>
        </div>

        <div class="viewer-summary">
          <template v-if="stats">
            <strong class="viewer-rate" :class="`rate--${rateTone}`" title="Pass rate">{{ passRate }}%</strong>
            <span v-if="stats.total" class="stack-bar viewer-bar" aria-hidden="true">
              <span class="stack-bar-seg stack-bar-seg--passed" :style="{ width: stats.shares.passed }"></span>
              <span class="stack-bar-seg stack-bar-seg--failed" :style="{ width: stats.shares.failed }"></span>
              <span class="stack-bar-seg stack-bar-seg--broken" :style="{ width: stats.shares.broken }"></span>
            </span>
          </template>

          <div class="viewer-actions">
            <button
              type="button"
              class="icon-button viewer-info-button"
              aria-label="Подробнее об отчёте"
              title="Подробнее об отчёте"
              :aria-expanded="openMenu === 'info'"
              aria-controls="viewer-info"
              @click="toggleMenu('info')"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8v.5" /></svg>
            </button>
            <a
              v-if="viewerSrc"
              class="icon-button"
              :href="viewerSrc"
              target="_blank"
              rel="noopener"
              aria-label="Открыть отдельно"
              title="Открыть отдельно"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true">
                <path d="M14 4h6v6M20 4l-9 9" />
                <path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" />
              </svg>
            </a>
            <button
              type="button"
              class="icon-button"
              aria-label="Ещё действия"
              title="Скачать или удалить"
              aria-haspopup="menu"
              :aria-expanded="openMenu === 'more'"
              @click="toggleMenu('more')"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h.5M12 12h.5M19 12h.5" /></svg>
            </button>
          </div>
        </div>

        <div v-if="openMenu === 'info'" id="viewer-info" class="viewer-popover viewer-info" role="dialog" aria-label="Об отчёте">
          <div v-if="stats" class="viewer-counts">
            <span><b>{{ stats.total }}</b> {{ pluralRu(stats.total, ['тест', 'теста', 'тестов']) }}</span>
            <span><i class="legend-dot legend-dot--passed"></i>пройдено <b>{{ stats.passed }}</b></span>
            <span><i class="legend-dot legend-dot--failed"></i>сбой <b>{{ stats.failed }}</b></span>
            <span><i class="legend-dot legend-dot--broken"></i>сломано <b>{{ stats.broken }}</b></span>
            <span>нестабильно <b>{{ stats.flaky }}</b></span>
            <span><i class="legend-dot legend-dot--other"></i>прочее <b>{{ stats.other }}</b></span>
          </div>
          <dl class="viewer-meta">
            <template v-if="parsed?.user">
              <dt>Автор</dt>
              <dd>{{ parsed.user }}</dd>
            </template>
            <template v-if="parsed">
              <dt>Прогон</dt>
              <dd>{{ parsed.date }}, {{ parsed.time }}</dd>
            </template>
            <template v-if="report.duration">
              <dt>Длительность</dt>
              <dd>{{ formatDuration(report.duration) }}</dd>
            </template>
            <dt>Загружен</dt>
            <dd>{{ formatDate(report.created_at) }}</dd>
            <dt>Размер</dt>
            <dd>{{ formatSize(report.size) }}</dd>
            <dt>ID</dt>
            <dd class="mono" :title="report.id">{{ report.id.slice(0, 8) }}</dd>
          </dl>
        </div>

        <div v-if="openMenu === 'more'" class="viewer-popover viewer-menu" role="menu">
          <button type="button" role="menuitem" @click="runAction('download')">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 4v12M7 11l5 5 5-5M4 20h16" /></svg>
            Скачать ZIP
          </button>
          <button type="button" role="menuitem" class="viewer-menu-danger" @click="runAction('delete')">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" /></svg>
            Удалить отчёт
          </button>
        </div>
      </header>

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
