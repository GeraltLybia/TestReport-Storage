<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import RunDetail from '../../components/common/runs/RunDetail.vue'
import RunsSidebar from '../../components/common/runs/RunsSidebar.vue'
import { useHistoryRuns } from '../../composables/useHistoryRuns'
import { useReports } from '../../composables/useReports'

const route = useRoute()
const router = useRouter()
const { reports } = useReports()
const runs = useHistoryRuns()
const { search, status } = runs

const selectedRunId = computed(() => (typeof route.params.runId === 'string' ? route.params.runId : null))
const selectedSummary = computed(() => runs.items.value.find((item) => item.uuid === selectedRunId.value) ?? null)

function selectRun(uuid: string) {
  if (uuid !== selectedRunId.value) router.push({ name: 'run-by-id', params: { runId: uuid } })
}
</script>

<template>
  <div class="runs-view">
    <header class="runs-head">
      <h1>Прогоны</h1>
      <p>
        Восстановлены из <code>history.jsonl</code> на сервере — {{ runs.counts.value.all }} прогонов. Полные
        Allure-отчёты — в разделе
        <RouterLink :to="{ name: 'reports' }">Отчёты</RouterLink>.
      </p>
    </header>

    <main class="runs-main">
      <RunsSidebar
        v-model:search="search"
        v-model:status="status"
        :items="runs.items.value"
        :total="runs.total.value"
        :counts="runs.counts.value"
        :loading="runs.loading.value"
        :error="runs.error.value"
        :selected-run-id="selectedRunId"
        @select="selectRun"
        @load-more="runs.loadMore()"
        @retry="runs.reload()"
      />
      <RunDetail :run-id="selectedRunId" :summary="selectedSummary" :reports="reports" />
    </main>
  </div>
</template>

<style scoped>
.runs-view {
  min-height: 100vh;
  max-width: 120rem;
  margin: 0 auto;
  padding: 1.75rem 2rem 2rem;
  display: flex;
  flex-direction: column;
  gap: 1.25rem;
}

.runs-head h1 {
  margin: 0;
  font-size: 1.75rem;
  font-weight: 700;
  letter-spacing: -0.02em;
  line-height: 1.2;
}

.runs-head p {
  margin: 0.35rem 0 0;
  color: var(--text-2);
}

.runs-head code {
  font-family: var(--font-mono);
  font-size: 0.85em;
}

.runs-head a {
  color: var(--accent-strong);
  font-weight: 600;
}

.runs-main {
  display: grid;
  grid-template-columns: 21rem minmax(0, 1fr);
  gap: 1rem;
  align-items: start;
}

@media (max-width: 900px) {
  .runs-main {
    grid-template-columns: minmax(0, 1fr);
  }
}

@media (max-width: 640px) {
  .runs-view {
    padding: 1.25rem 1rem 2rem;
  }
}
</style>
