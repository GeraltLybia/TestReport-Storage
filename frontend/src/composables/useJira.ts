import { ref, watch, type Ref } from 'vue'

import { fetchJiraConfig, fetchJiraLinks } from '../api/jira'
import type { JiraConfig, JiraIssueLink } from '../types/jira'

const DISABLED: JiraConfig = { enabled: false, baseUrl: null, projectKey: null, issueType: 'Bug' }
let configRequest: Promise<JiraConfig> | null = null

/** Jira settings of the backend, requested once per page load. */
export function useJiraConfig() {
  const config = ref<JiraConfig | null>(null)
  configRequest ??= fetchJiraConfig().catch(() => {
    configRequest = null
    return DISABLED
  })
  void configRequest.then((value) => (config.value = value))
  return config
}

/**
 * Issues filed for the failures of a report, by test id. Loaded when `enabled`
 * turns on (the results tab is open) and on demand after a bug is filed.
 */
export function useJiraLinks(reportId: Ref<string | null>, enabled: Ref<boolean>) {
  const links = ref<Record<string, JiraIssueLink>>({})
  let controller: AbortController | null = null

  async function load() {
    controller?.abort()
    const id = reportId.value
    if (!id || !enabled.value) return
    controller = new AbortController()
    const { signal } = controller
    try {
      const payload = await fetchJiraLinks(id, signal)
      if (!signal.aborted) links.value = payload.items
    } catch {
      // Chips are a hint: the results stay usable without them.
      if (!signal.aborted) links.value = {}
    }
  }

  watch(reportId, () => (links.value = {}))
  watch([reportId, enabled], () => void load(), { immediate: true })

  return { links, reload: load }
}
