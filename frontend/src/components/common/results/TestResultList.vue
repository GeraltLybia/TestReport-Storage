<script setup lang="ts">
import { computed, ref } from 'vue'

import { formatShortDuration, splitTestName, statusTone } from '../../../utils/reports'
import type { ResultStatusFilter, TestResultItem } from '../../../types/reports'

const props = defineProps<{
  items: TestResultItem[]
  total: number
  loading: boolean
  error: string | null
  incidentsCount?: number
}>()

const statusFilter = defineModel<ResultStatusFilter>('statusFilter', { required: true })

const emit = defineEmits<{
  retry: []
}>()

const query = ref('')

const rows = computed(() => {
  const needle = query.value.trim().toLowerCase()
  return props.items
    .filter(
      (item) =>
        !needle ||
        item.name.toLowerCase().includes(needle) ||
        (item.fullName ?? '').toLowerCase().includes(needle) ||
        (item.message ?? '').toLowerCase().includes(needle),
    )
    .map((item) => {
      const technical = splitTestName(item.fullName || item.name)
      const humanTitle = item.fullName && item.name !== item.fullName ? item.name : null
      return {
        ...item,
        tone: statusTone(item.status),
        title: humanTitle ?? technical.method,
        subtitle: humanTitle ? item.fullName : technical.module,
        durationText: formatShortDuration(item.duration),
        firstLine: item.message?.split('\n')[0] ?? '',
      }
    })
})
</script>

<template>
  <div class="results">
    <div class="results-toolbar">
      <div class="results-segmented" role="group" aria-label="Какие результаты показывать">
        <button type="button" :aria-pressed="statusFilter === 'incidents'" @click="statusFilter = 'incidents'">
          Падения<span v-if="incidentsCount !== undefined" class="results-count">{{ incidentsCount }}</span>
        </button>
        <button type="button" :aria-pressed="statusFilter === 'all'" @click="statusFilter = 'all'">Все тесты</button>
      </div>
      <label class="results-search">
        <span class="visually-hidden">Поиск по тестам</span>
        <input v-model="query" type="search" placeholder="Тест или текст ошибки" />
      </label>
    </div>

    <div v-if="error" class="results-state results-state--error" role="alert">
      <p>{{ error }}</p>
      <button type="button" class="link-button" @click="emit('retry')">Повторить</button>
    </div>
    <p v-else-if="loading && !items.length" class="results-state">Загрузка результатов…</p>
    <p v-else-if="!items.length" class="results-state">
      {{ statusFilter === 'incidents' ? 'Падений нет — все тесты прошли.' : 'В этом прогоне нет результатов.' }}
    </p>
    <p v-else-if="!rows.length" class="results-state">Ничего не найдено.</p>

    <ul v-else class="results-list" :aria-busy="loading">
      <li v-for="row in rows" :key="row.id" class="result" :class="`result--${row.tone}`">
        <details v-if="row.message" class="result-details">
          <summary class="result-row">
            <span class="result-icon" aria-hidden="true"></span>
            <span class="result-main">
              <span class="result-title">{{ row.title }}</span>
              <span v-if="row.subtitle" class="result-subtitle">{{ row.subtitle }}</span>
              <span class="result-first-line">{{ row.firstLine }}</span>
            </span>
            <span class="status-pill" :class="`status-pill--${row.tone}`">{{ row.status }}</span>
            <span class="result-duration">{{ row.durationText }}</span>
          </summary>
          <pre class="result-message">{{ row.message }}</pre>
        </details>
        <div v-else class="result-row">
          <span class="result-icon" aria-hidden="true"></span>
          <span class="result-main">
            <span class="result-title">{{ row.title }}</span>
            <span v-if="row.subtitle" class="result-subtitle">{{ row.subtitle }}</span>
          </span>
          <span class="status-pill" :class="`status-pill--${row.tone}`">{{ row.status }}</span>
          <span class="result-duration">{{ row.durationText }}</span>
        </div>
      </li>
    </ul>
    <p v-if="total > items.length" class="results-more muted">Показаны первые {{ items.length }} из {{ total }}</p>
  </div>
</template>

<style scoped src="../../../assets/style/components/results/TestResultList.css"></style>
