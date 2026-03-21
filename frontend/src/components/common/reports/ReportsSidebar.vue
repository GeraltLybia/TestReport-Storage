<script setup lang="ts">
import ReportListItem from './ReportListItem.vue'

import type { HistoryInfo, Report } from '../../../types/reports'

defineProps<{
  loading: boolean
  reports: Report[]
  selectedReportId: string | null
  historyInfo: HistoryInfo | null
  formatDate: (value: string | null) => string
  formatSize: (value: number) => string
  formatDuration: (value: number | null | undefined) => string
  getReportTitle: (report: Report) => string | undefined
}>()

const emit = defineEmits<{
  refresh: []
  selectReport: [id: string]
  downloadReport: [id: string]
  deleteReport: [id: string]
  downloadHistory: []
  uploadHistory: [event: Event]
}>()
</script>

<template>
  <section class="sidebar">
    <div class="sidebar-header">
      <div class="sidebar-title">
        <span>Отчеты</span>
        <span v-if="loading" class="chip">Загрузка…</span>
      </div>
      <button class="text-button" type="button" @click="emit('refresh')">
        Обновить
      </button>
    </div>

    <div v-if="!reports.length && !loading" class="empty-state">
      <p>Пока нет ни одного отчета.</p>
      <p>Загрузите ZIP c Allure отчетом, чтобы начать.</p>
    </div>

    <ul class="report-list">
      <ReportListItem
        v-for="report in reports"
        :key="report.id"
        :report="report"
        :active="report.id === selectedReportId"
        :format-date="formatDate"
        :format-size="formatSize"
        :format-duration="formatDuration"
        :get-report-title="getReportTitle"
        @select="emit('selectReport', $event)"
        @download="emit('downloadReport', $event)"
        @delete="emit('deleteReport', $event)"
      />
    </ul>

    <div class="history-card">
      <div class="history-header">
        <span>History</span>
        <span v-if="historyInfo" class="history-meta">
          {{ historyInfo.records }} записей ·
          {{ historyInfo.updated_at ? formatDate(historyInfo.updated_at) : 'нет данных' }}
        </span>
      </div>
      <div class="history-actions">
        <button
          type="button"
          class="text-button"
          @click="emit('downloadHistory')"
        >
          Скачать history.jsonl
        </button>
        <label class="text-button">
          Загрузить history.jsonl
          <input
            type="file"
            accept=".json,.jsonl"
            @change="emit('uploadHistory', $event)"
          />
        </label>
      </div>
    </div>
  </section>
</template>

<style scoped src="../../../assets/style/components/reports/ReportsSidebar.css"></style>
