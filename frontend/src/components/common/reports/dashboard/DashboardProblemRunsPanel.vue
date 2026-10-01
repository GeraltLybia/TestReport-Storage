<script setup lang="ts">
import { formatDate, getReportTitle } from '../../../../utils/reports'
import type { ProblemRunItem } from './types'

defineProps<{
  selectedReportId: string | null
  topProblemRuns: ProblemRunItem[]
}>()

const emit = defineEmits<{
  openReport: [id: string]
}>()
</script>

<template>
  <article class="panel panel--problems">
    <header class="panel-header">
      <div>
        <h2 class="panel-title">Проблемные прогоны</h2>
        <p class="panel-hint">Больше всего сбоев и поломок</p>
      </div>
      <RouterLink class="panel-link" :to="{ name: 'reports' }">Все отчёты →</RouterLink>
    </header>

    <p v-if="!topProblemRuns.length" class="panel-empty">Проблемных прогонов нет.</p>
    <div v-else class="problem-list">
      <button
        v-for="item in topProblemRuns"
        :key="item.report.id"
        type="button"
        class="problem-row"
        :class="{ 'problem-row--selected': item.report.id === selectedReportId }"
        @click="emit('openReport', item.report.id)"
      >
        <span class="problem-main">
          <span class="problem-name">{{ getReportTitle(item.report) }}</span>
          <span class="problem-meta">
            {{ formatDate(item.report.created_at) }} · {{ item.report.stats?.total ?? 0 }} тестов
          </span>
        </span>
        <span class="problem-pills">
          <span class="status-pill status-pill--failed">{{ item.report.stats?.failed ?? 0 }} сбоев</span>
          <span class="status-pill status-pill--broken">{{ item.report.stats?.broken ?? 0 }} слом.</span>
        </span>
        <strong class="problem-total" :aria-label="`${item.incidents} инцидентов`">{{ item.incidents }}</strong>
      </button>
    </div>
  </article>
</template>
