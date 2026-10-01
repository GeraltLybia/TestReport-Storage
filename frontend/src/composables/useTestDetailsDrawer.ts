import { ref } from 'vue'

import { fetchHistoryTestDetails } from '../api/reports'
import type { HistorySelectedTestDetails } from '../types/reports'

/**
 * The dashboard's test details drawer, opened from report and run results.
 * Details come from the history index, without dashboard filters.
 */
export function useTestDetailsDrawer() {
  const details = ref<HistorySelectedTestDetails | null>(null)
  const loadingKey = ref<string | null>(null)
  const error = ref<string | null>(null)
  let requestId = 0

  async function open(testKey: string) {
    const current = ++requestId
    loadingKey.value = testKey
    error.value = null
    try {
      const data = await fetchHistoryTestDetails(testKey, {})
      if (current === requestId) details.value = data
    } catch (exception) {
      if (current !== requestId) return
      details.value = null
      error.value = exception instanceof Error ? exception.message : 'Не удалось загрузить историю теста'
    } finally {
      if (current === requestId) loadingKey.value = null
    }
  }

  function close() {
    requestId++
    details.value = null
    loadingKey.value = null
  }

  function normalizeStatus(value: string | undefined) {
    return value?.trim().toLowerCase() ?? 'unknown'
  }

  return { details, loadingKey, error, open, close, normalizeStatus }
}
