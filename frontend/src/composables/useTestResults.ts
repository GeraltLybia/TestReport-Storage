import { ref, watch, type Ref } from 'vue'

import type { HistoryRunSummary, ResultChanges, ResultStatusFilter, TestResultItem } from '../types/reports'

type ResultsPage = { total: number; items: TestResultItem[]; run?: HistoryRunSummary; changes?: ResultChanges | null }
type Fetcher = (key: string, status: ResultStatusFilter, signal: AbortSignal) => Promise<ResultsPage>

/**
 * Loads test results for the entity identified by `key` (a report id or run uuid)
 * and reloads them when the key or the status filter changes. Stale responses
 * are aborted so fast switching never shows results of a previous selection.
 */
export function useTestResults(key: Ref<string | null>, fetcher: Fetcher, enabled: Ref<boolean> = ref(true)) {
  const statusFilter = ref<ResultStatusFilter>('incidents')
  const items = ref<TestResultItem[]>([])
  const total = ref(0)
  const run = ref<HistoryRunSummary | null>(null)
  const changes = ref<ResultChanges | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  let controller: AbortController | null = null

  async function load() {
    controller?.abort()
    const currentKey = key.value
    if (!currentKey || !enabled.value) return
    controller = new AbortController()
    const { signal } = controller
    loading.value = true
    error.value = null
    try {
      const page = await fetcher(currentKey, statusFilter.value, signal)
      if (signal.aborted) return
      items.value = page.items
      total.value = page.total
      run.value = page.run ?? null
      changes.value = page.changes ?? null
    } catch (exception) {
      if (signal.aborted) return
      items.value = []
      total.value = 0
      error.value = exception instanceof Error ? exception.message : 'Не удалось загрузить результаты'
    } finally {
      if (!signal.aborted) loading.value = false
    }
  }

  watch(key, () => {
    items.value = []
    total.value = 0
    run.value = null
    changes.value = null
    statusFilter.value = 'incidents'
  })

  watch([key, statusFilter, enabled], () => void load(), { immediate: true })

  return { statusFilter, items, total, run, changes, loading, error, reload: load }
}
