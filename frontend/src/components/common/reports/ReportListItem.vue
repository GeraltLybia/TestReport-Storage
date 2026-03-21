<script setup lang="ts">
import type { Report } from '../../../types/reports'

defineProps<{
  report: Report
  active: boolean
  formatDate: (value: string | null) => string
  formatSize: (value: number) => string
  formatDuration: (value: number | null | undefined) => string
  getReportTitle: (report: Report) => string | undefined
}>()

const emit = defineEmits<{
  select: [id: string]
  download: [id: string]
  delete: [id: string]
}>()
</script>

<template>
  <li
    class="report-item"
    :class="{ 'report-item--active': active }"
    @click="emit('select', report.id)"
  >
    <div class="report-main">
      <div class="report-name" :title="getReportTitle(report)">
        {{ getReportTitle(report) ?? report.id }}
      </div>
      <div class="report-meta">
        <span>{{ formatDate(report.created_at) }}</span>
        <span>·</span>
        <span>{{ formatSize(report.size) }}</span>
        <span>·</span>
        <span>Duration: {{ formatDuration(report.duration) }}</span>
        <span>·</span>
        <span class="report-id-short">
          {{ report.id.slice(0, 8) }}…
        </span>
      </div>
      <div v-if="report.status" class="report-status">
        <span
          class="stat-chip"
          :class="`status-chip status-chip--${report.status.toLowerCase()}`"
        >
          Status: {{ report.status }}
        </span>
      </div>
      <div v-if="report.stats" class="report-stats">
        <span class="stat-chip stat-chip--failed">
          Failed: {{ report.stats.failed }}
        </span>
        <span class="stat-chip stat-chip--passed">
          Passed: {{ report.stats.passed }}
        </span>
        <span class="stat-chip stat-chip--flaky">
          Flaky: {{ report.stats.flaky }}
        </span>
        <span class="stat-chip stat-chip--broken">
          Broken: {{ report.stats.broken }}
        </span>
        <span class="stat-chip">
          Total: {{ report.stats.total }}
        </span>
      </div>
    </div>
    <div class="report-actions">
      <button
        type="button"
        class="icon-button"
        title="Скачать ZIP"
        @click.stop="emit('download', report.id)"
      >
        ⬇
      </button>
      <button
        type="button"
        class="icon-button icon-button--danger"
        title="Удалить"
        @click.stop="emit('delete', report.id)"
      >
        ✕
      </button>
    </div>
  </li>
</template>

<style scoped src="../../../assets/style/components/reports/ReportListItem.css"></style>
