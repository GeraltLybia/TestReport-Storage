<script setup lang="ts">
import { computed, ref } from 'vue'

import ReportListItem from './ReportListItem.vue'
import { formatDate, getPassRate, getReportTitle, getReportTone, getRingStyle, getRingTitle } from '../../../utils/reports'
import type { HistoryInfo, Report } from '../../../types/reports'

const props = defineProps<{
  collapsed: boolean
  loading: boolean
  reports: Report[]
  selectedReportId: string | null
  historyInfo: HistoryInfo | null
}>()

const emit = defineEmits<{
  collapse: []
  expand: []
  refresh: []
  selectReport: [id: string]
  downloadHistory: []
  uploadHistory: [event: Event]
}>()

type StatusFilter = 'all' | 'failed' | 'broken' | 'passed'
const STATUS_FILTERS: { key: StatusFilter; label: string }[] = [
  { key: 'all', label: 'Все' },
  { key: 'failed', label: 'Failed' },
  { key: 'broken', label: 'Broken' },
  { key: 'passed', label: 'Passed' },
]

const query = ref('')
const statusFilter = ref<StatusFilter>('all')

const counts = computed(() => {
  const result: Record<StatusFilter, number> = { all: props.reports.length, failed: 0, broken: 0, passed: 0 }
  for (const report of props.reports) {
    const tone = getReportTone(report)
    if (tone === 'failed' || tone === 'broken' || tone === 'passed') result[tone] += 1
  }
  return result
})

const filteredReports = computed(() => {
  const needle = query.value.trim().toLowerCase()
  return props.reports.filter((report) => {
    if (statusFilter.value !== 'all' && getReportTone(report) !== statusFilter.value) return false
    if (!needle) return true
    return getReportTitle(report).toLowerCase().includes(needle) || report.id.toLowerCase().startsWith(needle)
  })
})
</script>

<template>
  <section class="sidebar" :class="{ 'sidebar--collapsed': collapsed }" aria-label="Список отчётов">
    <template v-if="collapsed">
      <button type="button" class="icon-button" aria-label="Развернуть список отчётов" @click="emit('expand')">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m13 6 6 6-6 6M6 6l6 6-6 6" /></svg>
      </button>
      <ul class="report-rail">
        <li v-for="report in reports" :key="report.id">
          <button
            type="button"
            class="report-rail-item"
            :class="{ 'report-rail-item--active': report.id === selectedReportId }"
            :title="getRingTitle(report)"
            :aria-label="getRingTitle(report)"
            @click="emit('selectReport', report.id)"
          >
            <span class="report-ring" :style="getRingStyle(report)">
              <span v-if="report.stats">{{ getPassRate(report) }}%</span>
            </span>
          </button>
        </li>
      </ul>
    </template>

    <template v-else>
      <div class="sidebar-toolbar">
        <label class="sidebar-search">
          <span class="visually-hidden">Поиск отчётов</span>
          <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></svg>
          <input v-model="query" type="search" placeholder="Поиск: имя, автор, ID" />
        </label>
        <button
          type="button"
          class="icon-button"
          :class="{ 'icon-button--spin': loading }"
          aria-label="Обновить список"
          title="Обновить список"
          @click="emit('refresh')"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M20 11a8 8 0 1 0-2.3 5.7M20 4v7h-7" /></svg>
        </button>
        <button
          type="button"
          class="icon-button"
          aria-label="Свернуть список отчётов"
          title="Свернуть список"
          @click="emit('collapse')"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="m11 6-6 6 6 6M18 6l-6 6 6 6" /></svg>
        </button>
      </div>

      <div class="segmented" role="group" aria-label="Фильтр по статусу">
        <button
          v-for="item in STATUS_FILTERS"
          :key="item.key"
          type="button"
          :aria-pressed="statusFilter === item.key"
          @click="statusFilter = item.key"
        >
          {{ item.label }}<span v-if="counts[item.key]" class="segmented-count">{{ counts[item.key] }}</span>
        </button>
      </div>

      <div v-if="!reports.length && !loading" class="sidebar-empty">
        <p>Пока нет ни одного отчёта.</p>
        <p>Загрузите ZIP с Allure-отчётом кнопкой в меню слева.</p>
      </div>
      <p v-else-if="!filteredReports.length" class="sidebar-empty">Ничего не найдено.</p>

      <ul class="report-list">
        <ReportListItem
          v-for="report in filteredReports"
          :key="report.id"
          :report="report"
          :active="report.id === selectedReportId"
          @select="emit('selectReport', $event)"
        />
      </ul>

      <div class="history-box">
        <div class="history-box-head">
          <span>history.jsonl</span>
          <span v-if="historyInfo" class="muted">
            {{ historyInfo.records }} записей<template v-if="historyInfo.updated_at">
              · {{ formatDate(historyInfo.updated_at) }}</template
            >
          </span>
        </div>
        <div class="history-box-actions">
          <button type="button" class="link-button" @click="emit('downloadHistory')">Скачать</button>
          <label class="link-button">
            Загрузить
            <input type="file" accept=".json,.jsonl" @change="emit('uploadHistory', $event)" />
          </label>
        </div>
      </div>
    </template>
  </section>
</template>

<style scoped src="../../../assets/style/components/reports/ReportsSidebar.css"></style>
