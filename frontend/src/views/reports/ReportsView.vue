<script setup lang="ts">
import { computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import ReportsSidebar from '../../components/common/reports/ReportsSidebar.vue'
import ReportViewer from '../../components/common/reports/ReportViewer.vue'
import { useReports } from '../../composables/useReports'

const {
  downloadHistory,
  error,
  handleDeleteReport,
  handleDownloadReport,
  handleHistoryUpload,
  historyInfo,
  loading,
  loadReports,
  reports,
  reportsLoaded,
  selectedReport,
  setSidebarCollapsed,
  selectedReportId,
  sidebarCollapsed,
  viewerSrc,
} = useReports()

const route = useRoute()
const router = useRouter()

const routeReportId = computed(() => {
  const value = route.params.reportId
  return typeof value === 'string' ? value : null
})

function openReport(id: string) {
  selectedReportId.value = id
  if (routeReportId.value !== id) {
    router.push({ name: 'report-by-id', params: { reportId: id } })
  }
}

watch(selectedReportId, (id) => {
  if (id && routeReportId.value !== id) {
    router.push({ name: 'report-by-id', params: { reportId: id } })
  }
})

watch(
  [reports, routeReportId, reportsLoaded],
  ([items, reportId, loaded]) => {
    if (!loaded) {
      return
    }

    if (items.length === 0) {
      selectedReportId.value = null
      if (reportId) {
        router.replace({ name: 'reports' })
      }
      return
    }

    if (reportId) {
      const exists = items.some((report) => report.id === reportId)
      if (exists) {
        selectedReportId.value = reportId
        return
      }

      selectedReportId.value = null
      router.replace({ name: 'reports' })
      return
    }

    if (!selectedReportId.value) {
      const firstReport = items[0]
      if (!firstReport) return
      const firstReportId = firstReport.id
      selectedReportId.value = firstReportId
      router.replace({ name: 'report-by-id', params: { reportId: firstReportId } })
    }
  },
  { immediate: true },
)
</script>

<template>
  <div class="reports-view">
    <header class="reports-head">
      <div>
        <h1>Отчёты</h1>
        <p>{{ reports.length }} Allure-отчётов в хранилище</p>
      </div>
    </header>

    <div v-if="error" class="reports-view-error" role="alert">
      <p>{{ error }}</p>
      <button type="button" class="text-button" @click="loadReports()">Повторить</button>
    </div>

    <main class="reports-view-main" :class="{ 'reports-view-main--collapsed': sidebarCollapsed }">
      <ReportsSidebar
        :collapsed="sidebarCollapsed"
        :loading="loading"
        :reports="reports"
        :selected-report-id="selectedReportId"
        :history-info="historyInfo"
        @refresh="loadReports"
        @collapse="setSidebarCollapsed(true)"
        @expand="setSidebarCollapsed(false)"
        @select-report="openReport"
        @download-history="downloadHistory"
        @upload-history="handleHistoryUpload"
      />

      <ReportViewer
        :report="selectedReport"
        :viewer-src="viewerSrc"
        @download="handleDownloadReport"
        @delete="handleDeleteReport"
      />
    </main>
  </div>
</template>

<style scoped src="../../assets/style/views/reports/ReportsView.css"></style>
