<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

import { deleteCoverageMeasurement, fetchCoverageMeasurements } from '../../api/coverage'
import { formatDate } from '../../utils/reports'
import type { CoverageKind, CoverageMeasurementMeta } from '../../types/coverage'

const items = ref<CoverageMeasurementMeta[]>([])
const loading = ref(true)
const error = ref<string | null>(null)
const kindFilter = ref<'all' | CoverageKind>('all')

async function load() {
  loading.value = true
  error.value = null
  try {
    items.value = await fetchCoverageMeasurements()
  } catch (exception) {
    error.value = exception instanceof Error ? exception.message : 'Не удалось загрузить измерения'
  } finally {
    loading.value = false
  }
}

async function remove(item: CoverageMeasurementMeta) {
  if (!window.confirm(`Удалить измерение «${item.name}»?`)) return
  try {
    await deleteCoverageMeasurement(item.id)
    items.value = items.value.filter((entry) => entry.id !== item.id)
  } catch (exception) {
    error.value = exception instanceof Error ? exception.message : 'Не удалось удалить измерение'
  }
}

const rows = computed(() =>
  items.value
    .filter((item) => kindFilter.value === 'all' || item.kind === kindFilter.value)
    .map((item) => {
      const summary = item.summary
      const covered = 'coveredOperations' in summary ? summary.coveredOperations : summary.coveredFields
      const total = 'operations' in summary ? summary.operations : summary.fields
      const unit = item.kind === 'rest' ? 'операций' : 'полей'
      const specTitle =
        item.kind === 'rest' && item.spec.title
          ? `${item.spec.title}${item.spec.version ? ` ${item.spec.version}` : ''}`
          : item.spec.filename
      return {
        ...item,
        specTitle,
        specMeta: item.kind === 'rest' ? item.spec.filename : item.spec.endpoint || 'все GraphQL-эндпоинты',
        coverage: summary.coverage,
        ratio: `${covered} из ${total} ${unit}`,
      }
    }),
)

onMounted(load)
</script>

<template>
  <div class="cov-view">
    <header class="cov-head">
      <div>
        <span class="cov-eyebrow">Покрытие API</span>
        <h1>Измерения покрытия</h1>
        <p>Каждое измерение — снимок: спецификация или схема и выбранные отчёты. Считается по log-вложениям тестов.</p>
      </div>
      <RouterLink class="cov-primary" :to="{ name: 'coverage-new' }">
        <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M12 5v14M5 12h14" /></svg>
        Новое измерение
      </RouterLink>
    </header>

    <div class="cov-segmented" role="group" aria-label="Тип измерения">
      <button type="button" :aria-pressed="kindFilter === 'all'" @click="kindFilter = 'all'">Все</button>
      <button type="button" :aria-pressed="kindFilter === 'rest'" @click="kindFilter = 'rest'">REST</button>
      <button type="button" :aria-pressed="kindFilter === 'graphql'" @click="kindFilter = 'graphql'">GraphQL</button>
    </div>

    <div v-if="error" class="cov-error" role="alert">
      <p>{{ error }}</p>
      <button type="button" class="cov-link" @click="load()">Повторить</button>
    </div>

    <section class="cov-card cov-table" aria-label="Измерения">
      <div class="cov-table-head cov-list-grid" aria-hidden="true">
        <span>Измерение</span><span>Тип</span><span>Спецификация</span><span>Отчёты</span><span>Покрытие</span><span></span>
      </div>
      <p v-if="loading && !items.length" class="cov-empty">Загрузка…</p>
      <div v-else-if="!rows.length" class="cov-empty">
        <p>Измерений пока нет.</p>
        <RouterLink class="cov-link" :to="{ name: 'coverage-new' }">Создать первое измерение</RouterLink>
      </div>
      <div v-for="row in rows" :key="row.id" class="cov-list-row cov-list-grid">
        <RouterLink class="cov-list-main" :to="{ name: 'coverage-by-id', params: { measurementId: row.id } }">
          <strong>{{ row.name }}</strong>
          <span>{{ formatDate(row.createdAt) }}</span>
        </RouterLink>
        <span><span class="cov-kind" :class="`cov-kind--${row.kind}`">{{ row.kind === 'rest' ? 'REST' : 'GraphQL' }}</span></span>
        <span class="cov-list-spec">
          <span class="cov-mono">{{ row.specTitle }}</span>
          <span>{{ row.specMeta }}</span>
        </span>
        <span class="cov-mono">{{ row.reports.length }}</span>
        <span class="cov-meter-cell" :title="row.ratio">
          <span class="cov-meter"><span :style="{ width: `${row.coverage}%` }"></span></span>
          <strong class="cov-mono">{{ row.coverage }}%</strong>
        </span>
        <button type="button" class="icon-button icon-button--danger" :aria-label="`Удалить ${row.name}`" @click="remove(row)">
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" /></svg>
        </button>
      </div>
    </section>
  </div>
</template>

<style src="../../assets/style/views/coverage/Coverage.css"></style>
