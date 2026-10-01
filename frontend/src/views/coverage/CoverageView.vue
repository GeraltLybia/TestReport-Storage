<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRoute } from 'vue-router'

import GraphqlCoverage from '../../components/common/coverage/GraphqlCoverage.vue'
import RestCoverage from '../../components/common/coverage/RestCoverage.vue'
import { fetchCoverageMeasurement } from '../../api/coverage'
import { formatDate } from '../../utils/reports'
import type { CoverageMeasurement } from '../../types/coverage'

const route = useRoute()
const measurement = ref<CoverageMeasurement | null>(null)
const loading = ref(true)
const error = ref<string | null>(null)
let controller: AbortController | null = null

const measurementId = computed(() => (typeof route.params.measurementId === 'string' ? route.params.measurementId : ''))

async function load() {
  controller?.abort()
  controller = new AbortController()
  const { signal } = controller
  loading.value = true
  error.value = null
  try {
    measurement.value = await fetchCoverageMeasurement(measurementId.value, signal)
  } catch (exception) {
    if (signal.aborted) return
    error.value = exception instanceof Error ? exception.message : 'Не удалось загрузить измерение'
  } finally {
    if (!signal.aborted) loading.value = false
  }
}

watch(measurementId, () => void load(), { immediate: true })

const specLine = computed(() => {
  const m = measurement.value
  if (!m) return ''
  if (m.kind === 'rest') {
    const title = [m.spec.title, m.spec.version].filter(Boolean).join(' ')
    return [title || m.spec.filename, m.spec.basePath, ...(m.spec.hosts ?? [])].filter(Boolean).join(' · ')
  }
  return [m.spec.filename, m.spec.endpoint].filter(Boolean).join(' · ')
})
</script>

<template>
  <div class="cov-view">
    <p v-if="loading && !measurement" class="cov-empty">Загрузка измерения…</p>
    <div v-else-if="error" class="cov-error" role="alert">
      <p>{{ error }}</p>
      <RouterLink class="cov-link" :to="{ name: 'coverage' }">К списку измерений</RouterLink>
    </div>
    <template v-else-if="measurement">
      <header class="cov-head">
        <div>
          <span class="cov-eyebrow">Покрытие API · {{ measurement.kind === 'rest' ? 'REST' : 'GraphQL' }}</span>
          <h1>{{ measurement.name }}</h1>
          <p>
            <span class="cov-mono">{{ specLine }}</span> · {{ measurement.reports.length }}
            {{ measurement.reports.length === 1 ? 'отчёт' : 'отчётов' }} · {{ measurement.summary.calls }} запросов ·
            {{ formatDate(measurement.createdAt) }}
          </p>
        </div>
        <RouterLink class="cov-ghost" :to="{ name: 'coverage' }">Все измерения</RouterLink>
      </header>

      <details class="cov-card cov-reports-used">
        <summary>Отчёты в измерении</summary>
        <ul>
          <li v-for="report in measurement.reports" :key="report.id">
            <RouterLink :to="{ name: 'report-by-id', params: { reportId: report.id } }">{{ report.name }}</RouterLink>
          </li>
        </ul>
      </details>

      <RestCoverage v-if="measurement.result.kind === 'rest'" :result="measurement.result" />
      <GraphqlCoverage v-else :result="measurement.result" />
    </template>
  </div>
</template>

<style src="../../assets/style/views/coverage/Coverage.css"></style>
