<script setup lang="ts">
import { computed } from 'vue'

import { formatShortDuration, parseReportName, statusTone } from '../../../utils/reports'
import type { HistoryRunSummary, RunStatusFilter } from '../../../types/reports'

const props = defineProps<{
  items: HistoryRunSummary[]
  total: number
  counts: Record<RunStatusFilter, number>
  loading: boolean
  error: string | null
  selectedRunId: string | null
}>()

const search = defineModel<string>('search', { required: true })
const status = defineModel<RunStatusFilter>('status', { required: true })

const emit = defineEmits<{
  select: [uuid: string]
  loadMore: []
  retry: []
}>()

const STATUS_FILTERS: { key: RunStatusFilter; label: string }[] = [
  { key: 'all', label: 'Все' },
  { key: 'failed', label: 'Failed' },
  { key: 'broken', label: 'Broken' },
  { key: 'passed', label: 'Passed' },
]

function describe(run: HistoryRunSummary) {
  const parsed = parseReportName(run.name)
  const when = new Date(run.timestamp)
  const fallback = Number.isNaN(when.getTime())
    ? run.name
    : when.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit' })
  return {
    title: parsed ? `${parsed.date} · ${parsed.time}` : fallback,
    meta: [
      parsed?.user,
      `${run.total} ${run.total === 1 ? 'тест' : 'тестов'}`,
      run.duration ? formatShortDuration(run.duration) : null,
    ]
      .filter(Boolean)
      .join(' · '),
    tone: statusTone(run.status),
    rateTone: run.passRate < 70 ? 'failed' : run.passRate < 90 ? 'broken' : 'ok',
    passedShare: share(run, run.passed),
    failedShare: share(run, run.failed),
    brokenShare: share(run, run.broken),
  }
}

function share(run: HistoryRunSummary, value: number) {
  return `${run.total ? (value / run.total) * 100 : 0}%`
}

const rows = computed(() => props.items.map((run) => ({ run, ...describe(run) })))
</script>

<template>
  <section class="sidebar" aria-label="Список прогонов">
    <div class="sidebar-toolbar">
      <label class="sidebar-search">
        <span class="visually-hidden">Поиск прогонов</span>
        <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></svg>
        <input v-model="search" type="search" placeholder="Поиск: имя, автор, UUID" />
      </label>
    </div>

    <div class="segmented" role="group" aria-label="Фильтр по статусу">
      <button
        v-for="item in STATUS_FILTERS"
        :key="item.key"
        type="button"
        :aria-pressed="status === item.key"
        @click="status = item.key"
      >
        {{ item.label }}<span v-if="counts[item.key]" class="segmented-count">{{ counts[item.key] }}</span>
      </button>
    </div>

    <div v-if="error" class="sidebar-empty" role="alert">
      <p>{{ error }}</p>
      <button type="button" class="link-button" @click="emit('retry')">Повторить</button>
    </div>
    <p v-else-if="!items.length && !loading" class="sidebar-empty">
      {{ search || status !== 'all' ? 'Ничего не найдено.' : 'История пуста — загрузите history.jsonl.' }}
    </p>

    <ul class="report-list" :aria-busy="loading">
      <li v-for="{ run, title, meta, tone, rateTone, passedShare, failedShare, brokenShare } in rows" :key="run.uuid">
        <button
          type="button"
          class="report-item"
          :class="{ 'report-item--active': run.uuid === selectedRunId }"
          :aria-current="run.uuid === selectedRunId ? 'true' : undefined"
          :title="run.name"
          @click="emit('select', run.uuid)"
        >
          <span class="report-icon" :class="`report-icon--${tone}`" aria-hidden="true">
            <svg v-if="tone === 'failed'" viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18" /></svg>
            <svg v-else-if="tone === 'broken'" viewBox="0 0 24 24"><path d="M12 5v9M12 19v.5" /></svg>
            <svg v-else-if="tone === 'passed'" viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7" /></svg>
            <svg v-else viewBox="0 0 24 24"><path d="M6 12h12" /></svg>
          </span>
          <span class="report-main">
            <span class="report-name">{{ title }}</span>
            <span class="report-meta">{{ meta }}</span>
          </span>
          <span v-if="run.total" class="report-score">
            <span class="mono-strong" :class="`rate--${rateTone}`">{{ run.passRate }}%</span>
            <span class="stack-bar report-bar">
              <span class="stack-bar-seg stack-bar-seg--passed" :style="{ width: passedShare }"></span>
              <span class="stack-bar-seg stack-bar-seg--failed" :style="{ width: failedShare }"></span>
              <span class="stack-bar-seg stack-bar-seg--broken" :style="{ width: brokenShare }"></span>
            </span>
          </span>
        </button>
      </li>
    </ul>

    <button v-if="items.length < total" type="button" class="load-more" :disabled="loading" @click="emit('loadMore')">
      {{ loading ? 'Загрузка…' : `Показать ещё (${total - items.length})` }}
    </button>
  </section>
</template>

<style scoped src="../../../assets/style/components/reports/ReportsSidebar.css"></style>
<style scoped src="../../../assets/style/components/reports/ReportListItem.css"></style>
<style scoped>
.load-more {
  min-height: 2.5rem;
  border: 1px dashed var(--border-strong);
  border-radius: 10px;
  background: transparent;
  color: var(--accent-strong);
  font: inherit;
  font-size: 0.85rem;
  font-weight: 600;
  cursor: pointer;
}

.load-more:disabled {
  color: var(--text-3);
  cursor: progress;
}
</style>
