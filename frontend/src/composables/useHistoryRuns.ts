import { onBeforeUnmount, ref, watch } from 'vue'

import { fetchHistoryRuns } from '../api/reports'
import type { HistoryRunSummary, RunStatusFilter } from '../types/reports'

const PAGE_SIZE = 50
const SEARCH_DEBOUNCE_MS = 250

/** Paged list of runs restored from the server-side history index. */
export function useHistoryRuns() {
  const search = ref('')
  const status = ref<RunStatusFilter>('all')
  const items = ref<HistoryRunSummary[]>([])
  const total = ref(0)
  const counts = ref<Record<RunStatusFilter, number>>({ all: 0, failed: 0, broken: 0, passed: 0 })
  const loading = ref(false)
  const error = ref<string | null>(null)
  let controller: AbortController | null = null
  let debounceTimer: ReturnType<typeof setTimeout> | undefined

  async function load(append = false) {
    controller?.abort()
    controller = new AbortController()
    const { signal } = controller
    loading.value = true
    error.value = null
    try {
      const page = await fetchHistoryRuns(
        { search: search.value, status: status.value, limit: PAGE_SIZE, offset: append ? items.value.length : 0 },
        signal,
      )
      if (signal.aborted) return
      items.value = append ? [...items.value, ...page.items] : page.items
      total.value = page.total
      counts.value = page.counts
    } catch (exception) {
      if (signal.aborted) return
      error.value = exception instanceof Error ? exception.message : 'Не удалось загрузить прогоны'
    } finally {
      if (!signal.aborted) loading.value = false
    }
  }

  watch(status, () => void load())
  watch(search, () => {
    clearTimeout(debounceTimer)
    debounceTimer = setTimeout(() => void load(), SEARCH_DEBOUNCE_MS)
  })

  onBeforeUnmount(() => {
    clearTimeout(debounceTimer)
    controller?.abort()
  })

  void load()

  return {
    search,
    status,
    items,
    total,
    counts,
    loading,
    error,
    reload: () => load(),
    loadMore: () => load(true),
  }
}
