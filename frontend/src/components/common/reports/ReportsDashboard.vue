<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'

import DashboardFailureSignaturesPanel from './dashboard/DashboardFailureSignaturesPanel.vue'
import DashboardHealthPanel from './dashboard/DashboardHealthPanel.vue'
import DashboardProblemRunsPanel from './dashboard/DashboardProblemRunsPanel.vue'
import DashboardStabilityModal from './dashboard/DashboardStabilityModal.vue'
import DashboardTagHealthPanel from './dashboard/DashboardTagHealthPanel.vue'
import DashboardTestDetailsPanel from './dashboard/DashboardTestDetailsPanel.vue'
import DashboardTrendPanel from './dashboard/DashboardTrendPanel.vue'
import DashboardUnstablePanel from './dashboard/DashboardUnstablePanel.vue'
import { useReportsDashboard } from '../../../composables/useReportsDashboard'
import { formatDuration } from '../../../utils/reports'
import type { Report } from '../../../types/reports'

const props = defineProps<{
  reports: Report[]
  selectedReportId: string | null
}>()

const {
  activeDateFrom,
  activeDateTo,
  activeEnvironment,
  activeSignature,
  activeTags,
  activeSuite,
  aggregateStats,
  closeTestDetails,
  dashboardError,
  dateFromMax,
  dateToMin,
  failureSignatures,
  filterOptions,
  filteredRunCount,
  filteredStabilityDialogItems,
  historyLoading,
  incidentRate,
  normalizeStatus,
  openReport,
  p95Duration,
  passRate,
  resetFilters,
  retryDashboard,
  selectTest,
  selectedTestDetails,
  setActiveStabilityBucket,
  setStabilitySearch,
  stabilityDialog,
  stabilitySearch,
  stabilitySummary,
  tagHealth,
  toggleSignature,
  toggleTag,
  topProblemRuns,
  topUnstableTests,
  trendPoints,
} = useReportsDashboard(props)

const router = useRouter()

const hasActiveFilters = computed(
  () =>
    activeTags.value.length > 0 ||
    activeSuite.value !== 'all' ||
    activeEnvironment.value !== 'all' ||
    activeSignature.value !== 'all' ||
    Boolean(activeDateFrom.value) ||
    Boolean(activeDateTo.value),
)

const statusShares = computed(() => {
  const { total, passed, failed, broken } = aggregateStats.value
  const share = (value: number) => `${total ? (value / total) * 100 : 0}%`
  return { passed: share(passed), failed: share(failed), broken: share(broken) }
})

const flakyShare = computed(() => {
  const { uniqueTests, flaky } = stabilitySummary.value
  return uniqueTests ? Math.round((flaky / uniqueTests) * 100) : 0
})

// Technical labels (pytestrail(...), @pytest.mark...) go after the human tags.
const TECHNICAL_TAG = /^(@?pytest|pytestrail)/
const TAGS_COLLAPSED_LIMIT = 14
const tagQuery = ref('')
const tagsExpanded = ref(false)

const sortedTags = computed(() => {
  const tags = [...filterOptions.value.tags]
  return tags.sort((left, right) => {
    const technical = Number(TECHNICAL_TAG.test(left)) - Number(TECHNICAL_TAG.test(right))
    return technical || left.localeCompare(right)
  })
})

const visibleTags = computed(() => {
  const query = tagQuery.value.trim().toLowerCase()
  if (query) return sortedTags.value.filter((tag) => tag.toLowerCase().includes(query))
  if (tagsExpanded.value) return sortedTags.value
  const head = sortedTags.value.slice(0, TAGS_COLLAPSED_LIMIT)
  const selectedOutside = activeTags.value.filter((tag) => !head.includes(tag))
  return [...head, ...selectedOutside]
})

const hiddenTagsCount = computed(() =>
  tagQuery.value.trim() || tagsExpanded.value ? 0 : Math.max(0, sortedTags.value.length - visibleTags.value.length),
)

const lastRunLabel = computed(() => trendPoints.value[trendPoints.value.length - 1]?.label ?? null)
</script>

<template>
  <section class="dashboard" aria-label="Дашборд">
    <header class="dashboard-head">
      <div class="dashboard-copy">
        <span class="dashboard-eyebrow">Auto QA Observatory</span>
        <h1>Качество и стабильность</h1>
        <p>
          Метрики по <code>history.jsonl</code>: история тестов, нестабильность, сигнатуры падений и теги
        </p>
      </div>
      <p v-if="lastRunLabel" class="dashboard-last-run">
        <span class="legend-dot legend-dot--passed"></span>
        Последний прогон: {{ lastRunLabel }}
      </p>
    </header>

    <section class="dashboard-filters" aria-label="Фильтры">
      <div class="filters-grid">
        <label class="filter-field">
          <span>Suite</span>
          <span class="select-wrap">
            <select v-model="activeSuite">
              <option value="all">Все suite</option>
              <option v-for="suite in filterOptions.suites" :key="suite" :value="suite">{{ suite }}</option>
            </select>
          </span>
        </label>

        <label class="filter-field">
          <span>Environment</span>
          <span class="select-wrap">
            <select v-model="activeEnvironment">
              <option value="all">Все environment</option>
              <option v-for="environment in filterOptions.environments" :key="environment" :value="environment">
                {{ environment }}
              </option>
            </select>
          </span>
        </label>

        <label class="filter-field">
          <span>Сигнатура сбоя</span>
          <span class="select-wrap">
            <select v-model="activeSignature">
              <option value="all">Все сигнатуры</option>
              <option v-for="item in failureSignatures" :key="item.signature" :value="item.signature">
                {{ item.signature }}
              </option>
            </select>
          </span>
        </label>

        <div class="filter-field">
          <span id="period-label">Период</span>
          <div class="date-range" role="group" aria-labelledby="period-label">
            <input v-model="activeDateFrom" :max="dateFromMax" type="date" aria-label="С даты" />
            <span aria-hidden="true">→</span>
            <input v-model="activeDateTo" :min="dateToMin" type="date" aria-label="По дату" />
          </div>
        </div>
      </div>

      <div class="tag-filter">
        <span class="tag-filter-label">Теги</span>
        <input
          v-if="filterOptions.tags.length > TAGS_COLLAPSED_LIMIT"
          v-model="tagQuery"
          type="search"
          class="tag-search"
          :placeholder="`Найти среди ${filterOptions.tags.length} тегов`"
          aria-label="Поиск по тегам"
        />
        <button
          type="button"
          class="chip"
          :class="{ 'chip--active': activeTags.length === 0 }"
          :aria-pressed="activeTags.length === 0"
          @click="activeTags = []"
        >
          Все теги
        </button>
        <button
          v-for="tag in visibleTags"
          :key="tag"
          type="button"
          class="chip"
          :class="{ 'chip--active': activeTags.includes(tag) }"
          :aria-pressed="activeTags.includes(tag)"
          @click="toggleTag(tag)"
        >
          {{ tag }}
        </button>
        <span v-if="tagQuery && !visibleTags.length" class="muted">Ничего не найдено</span>
        <button v-if="hiddenTagsCount" type="button" class="chip chip--more" @click="tagsExpanded = true">
          Ещё {{ hiddenTagsCount }}
        </button>
        <button v-else-if="tagsExpanded && !tagQuery" type="button" class="chip chip--more" @click="tagsExpanded = false">
          Свернуть
        </button>
        <button v-if="hasActiveFilters" type="button" class="filter-reset" @click="resetFilters()">
          Сбросить фильтры
        </button>
      </div>
    </section>

    <div v-if="historyLoading && !filteredRunCount" class="dashboard-state">Загрузка history.jsonl…</div>

    <div v-else-if="dashboardError" class="dashboard-state dashboard-state--error" role="alert">
      <p>{{ dashboardError }}</p>
      <button type="button" class="filter-reset" @click="retryDashboard()">Повторить</button>
    </div>

    <div v-else-if="!filteredRunCount" class="dashboard-state">
      <p>С текущими фильтрами данных нет.</p>
      <p>Сбрось фильтры или загрузи отчёт с <code>history.jsonl</code>.</p>
    </div>

    <template v-else>
      <section class="kpi-grid" aria-label="Ключевые метрики" :aria-busy="historyLoading">
        <article class="kpi">
          <div class="kpi-top">
            <span class="kpi-label">Pass rate</span>
            <span v-if="incidentRate" class="status-pill status-pill--failed">риск {{ incidentRate }}%</span>
          </div>
          <strong class="kpi-value">{{ passRate }}%</strong>
          <span class="stack-bar" aria-hidden="true">
            <span class="stack-bar-seg stack-bar-seg--passed" :style="{ width: statusShares.passed }"></span>
            <span class="stack-bar-seg stack-bar-seg--failed" :style="{ width: statusShares.failed }"></span>
            <span class="stack-bar-seg stack-bar-seg--broken" :style="{ width: statusShares.broken }"></span>
          </span>
        </article>
        <article class="kpi">
          <span class="kpi-label">Прогонов</span>
          <strong class="kpi-value">{{ filteredRunCount }}</strong>
          <span class="kpi-note">после фильтрации</span>
        </article>
        <article class="kpi">
          <span class="kpi-label">Уникальных тестов</span>
          <strong class="kpi-value">{{ stabilitySummary.uniqueTests }}</strong>
          <span class="kpi-note">историй тест-кейсов</span>
        </article>
        <button type="button" class="kpi kpi--button" @click="setActiveStabilityBucket('flaky')">
          <span class="kpi-label">Нестабильные тесты</span>
          <strong class="kpi-value tone-broken">{{ stabilitySummary.flaky }}</strong>
          <span class="kpi-note">{{ flakyShare }}% от всех тестов</span>
        </button>
        <article class="kpi">
          <span class="kpi-label">P95 длительность</span>
          <strong class="kpi-value">{{ formatDuration(p95Duration) }}</strong>
          <span class="kpi-note">длинный хвост выполнения</span>
        </article>
      </section>

      <div class="dashboard-row">
        <DashboardTrendPanel
          class="dashboard-row-main"
          :trend-points="trendPoints"
          @open-report="openReport($event)"
          @open-run="router.push({ name: 'run-by-id', params: { runId: $event } })"
        />
        <DashboardHealthPanel
          class="dashboard-row-side"
          :aggregate-stats="aggregateStats"
          :pass-rate="passRate"
          :stability-summary="stabilitySummary"
          @open-bucket="setActiveStabilityBucket($event)"
        />
      </div>

      <div class="dashboard-row">
        <DashboardUnstablePanel
          class="dashboard-row-main"
          :top-unstable-tests="topUnstableTests"
          :flaky-count="stabilitySummary.flaky"
          @select-test="selectTest($event)"
          @open-bucket="setActiveStabilityBucket($event)"
        />
        <DashboardFailureSignaturesPanel
          class="dashboard-row-side"
          :active-signature="activeSignature"
          :failure-signatures="failureSignatures"
          @toggle-signature="toggleSignature($event)"
        />
      </div>

      <div class="dashboard-row dashboard-row--even">
        <DashboardTagHealthPanel :active-tags="activeTags" :tag-health="tagHealth" @toggle-tag="toggleTag($event)" />
        <DashboardProblemRunsPanel
          :selected-report-id="selectedReportId"
          :top-problem-runs="topProblemRuns"
          @open-report="openReport($event)"
        />
      </div>
    </template>

    <DashboardStabilityModal
      v-if="stabilityDialog"
      :items="filteredStabilityDialogItems"
      :search="stabilitySearch"
      :title="stabilityDialog.title"
      @close="setActiveStabilityBucket(null)"
      @select-test="selectTest($event)"
      @update-search="setStabilitySearch($event)"
    />

    <DashboardTestDetailsPanel
      v-if="selectedTestDetails"
      :selected-test-details="selectedTestDetails"
      :normalize-status="normalizeStatus"
      @close="closeTestDetails()"
    />
  </section>
</template>

<style src="../../../assets/style/components/reports/ReportsDashboard.css"></style>
