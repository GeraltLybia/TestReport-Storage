import { computed, onMounted, ref } from 'vue'

import {
  deleteReport,
  fetchHistoryInfo,
  fetchReports,
  uploadHistory,
  uploadReport,
} from './api'
import { formatDate, formatDuration, formatSize, getReportTitle } from './utils'
import type { HistoryInfo, Report } from './types'

export function useReports() {
  const reports = ref<Report[]>([])
  const selectedReportId = ref<string | null>(null)
  const loading = ref(false)
  const uploading = ref(false)
  const error = ref<string | null>(null)
  const historyInfo = ref<HistoryInfo | null>(null)
  const sidebarVisible = ref(true)

  const selectedReport = computed(() => {
    if (!selectedReportId.value) return null
    return reports.value.find((report) => report.id === selectedReportId.value) ?? null
  })

  const viewerSrc = computed(() => {
    if (!selectedReport.value) return null
    if (selectedReport.value.entry_path) {
      return `/reports-static/${selectedReport.value.entry_path}`
    }
    return `/reports-static/${selectedReport.value.id}/index.html`
  })

  async function loadReports() {
    try {
      loading.value = true
      error.value = null
      const data = await fetchReports()
      reports.value = data

      const firstReport = data.length > 0 ? data[0] : undefined
      if (!selectedReportId.value && firstReport) {
        selectedReportId.value = firstReport.id
      }
    } catch (exception) {
      error.value = (exception as Error).message
    } finally {
      loading.value = false
    }
  }

  async function loadHistoryInfo() {
    try {
      historyInfo.value = await fetchHistoryInfo()
    } catch {
      // No-op for this side panel widget.
    }
  }

  async function handleUploadReport(event: Event) {
    const input = event.target as HTMLInputElement
    const file = input.files?.[0]
    if (!file) return

    uploading.value = true
    error.value = null
    try {
      await uploadReport(file)
      await loadReports()
    } catch (exception) {
      error.value = (exception as Error).message
    } finally {
      uploading.value = false
      input.value = ''
    }
  }

  async function handleDeleteReport(id: string) {
    if (!window.confirm('Удалить отчет?')) return

    error.value = null
    try {
      await deleteReport(id)
      reports.value = reports.value.filter((report) => report.id !== id)
      if (selectedReportId.value === id) {
        selectedReportId.value = null
      }
    } catch (exception) {
      error.value = (exception as Error).message
    }
  }

  function handleDownloadReport(id: string) {
    window.open(`/api/reports/${id}/download`, '_blank')
  }

  async function handleHistoryUpload(event: Event) {
    const input = event.target as HTMLInputElement
    const file = input.files?.[0]
    if (!file) return

    error.value = null
    try {
      await uploadHistory(file)
      await loadHistoryInfo()
    } catch (exception) {
      error.value = (exception as Error).message
    } finally {
      input.value = ''
    }
  }

  function downloadHistory() {
    window.location.href = '/api/history'
  }

  onMounted(() => {
    loadReports()
    loadHistoryInfo()
  })

  return {
    downloadHistory,
    error,
    formatDate,
    formatDuration,
    formatSize,
    getReportTitle,
    handleDeleteReport,
    handleDownloadReport,
    handleHistoryUpload,
    handleUploadReport,
    historyInfo,
    loading,
    loadReports,
    reports,
    selectedReportId,
    sidebarVisible,
    uploading,
    viewerSrc,
  }
}
