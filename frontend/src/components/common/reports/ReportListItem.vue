<script setup lang="ts">
import { computed } from 'vue'

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
  report: Report
  active: boolean
}>()

const emit = defineEmits<{
  select: [id: string]
}>()

const title = computed(() => getReportTitle(props.report))
const parsed = computed(() => parseReportName(title.value))
const tone = computed(() => getReportTone(props.report))

const meta = computed(() => {
  const stats = props.report.stats
  return [
    parsed.value?.user,
    stats ? `${stats.total} ${stats.total === 1 ? 'тест' : 'тестов'}` : null,
    props.report.duration ? formatDuration(props.report.duration) : null,
    formatSize(props.report.size),
  ]
    .filter(Boolean)
    .join(' · ')
})

const shares = computed(() => {
  const s = props.report.stats
  const share = (value: number) => `${s && s.total ? (value / s.total) * 100 : 0}%`
  return { passed: share(s?.passed ?? 0), failed: share(s?.failed ?? 0), broken: share(s?.broken ?? 0) }
})

const passRate = computed(() => getPassRate(props.report))
const rateTone = computed(() => (passRate.value < 70 ? 'failed' : passRate.value < 90 ? 'broken' : 'ok'))
</script>

<template>
  <li>
    <button
      type="button"
      class="report-item"
      :class="{ 'report-item--active': active }"
      :aria-current="active ? 'true' : undefined"
      :title="title"
      @click="emit('select', report.id)"
    >
      <span class="report-icon" :class="`report-icon--${tone}`" aria-hidden="true">
        <svg v-if="tone === 'failed'" viewBox="0 0 24 24"><path d="M6 6l12 12M18 6L6 18" /></svg>
        <svg v-else-if="tone === 'broken'" viewBox="0 0 24 24"><path d="M12 5v9M12 19v.5" /></svg>
        <svg v-else-if="tone === 'passed'" viewBox="0 0 24 24"><path d="M5 12.5l4.5 4.5L19 7" /></svg>
        <svg v-else viewBox="0 0 24 24"><path d="M6 12h12" /></svg>
      </span>
      <span class="report-main">
        <span class="report-name">
          <template v-if="parsed">{{ parsed.date }} · {{ parsed.time }}</template>
          <template v-else>{{ title }}</template>
        </span>
        <span class="report-meta">{{ meta || formatDate(report.created_at) }}</span>
      </span>
      <span v-if="report.stats?.total" class="report-score">
        <span class="mono-strong" :class="`rate--${rateTone}`">{{ passRate }}%</span>
        <span class="stack-bar report-bar">
          <span class="stack-bar-seg stack-bar-seg--passed" :style="{ width: shares.passed }"></span>
          <span class="stack-bar-seg stack-bar-seg--failed" :style="{ width: shares.failed }"></span>
          <span class="stack-bar-seg stack-bar-seg--broken" :style="{ width: shares.broken }"></span>
        </span>
      </span>
    </button>
  </li>
</template>

<style scoped src="../../../assets/style/components/reports/ReportListItem.css"></style>
