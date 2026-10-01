<script setup lang="ts">
import { computed, ref } from 'vue'

import { describeChange, formatDate, formatShortDuration, pluralRu, splitTestName, statusTone } from '../../../utils/reports'
import type { ResultChanges, ResultStatusFilter, TestResultItem } from '../../../types/reports'

const props = defineProps<{
  items: TestResultItem[]
  total: number
  loading: boolean
  error: string | null
  incidentsCount?: number
  /** Comparison with previous runs; null when there is no history. */
  changes?: ResultChanges | null
  /** Test key whose history is being loaded, to show a spinner on its button. */
  openingTestKey?: string | null
}>()

const statusFilter = defineModel<ResultStatusFilter>('statusFilter', { required: true })

const emit = defineEmits<{
  retry: []
  openTest: [testKey: string]
}>()

const query = ref('')

const STAT_FILTER: Record<string, ResultStatusFilter> = {
  'still-failing': 'incidents',
  'new-test': 'all',
}

const changeStats = computed(() => {
  const changes = props.changes
  if (!changes) return []
  return [
    {
      key: 'new-failure',
      count: changes.newFailures,
      label: pluralRu(changes.newFailures, ['новое падение', 'новых падения', 'новых падений']),
    },
    {
      key: 'still-failing',
      count: changes.stillFailing,
      label: pluralRu(changes.stillFailing, ['падает повторно', 'падают повторно', 'падают повторно']),
    },
    { key: 'fixed', count: changes.fixed, label: pluralRu(changes.fixed, ['починен', 'починены', 'починены']) },
    {
      key: 'new-test',
      count: changes.newTests,
      label: pluralRu(changes.newTests, ['новый тест', 'новых теста', 'новых тестов']),
    },
  ]
})

const visibleChangeStats = computed(() => changeStats.value.filter((stat) => stat.count > 0))

const changesCount = computed(() =>
  props.changes ? props.changes.newFailures + props.changes.fixed : undefined,
)

function previousText(item: TestResultItem) {
  const previous = item.previous
  if (!previous) return 'В истории этого теста ещё не было'
  const when = previous.at ? formatDate(new Date(previous.at).toISOString()) : ''
  return `Ранее: ${previous.status}${when ? ` · ${when}` : ''}${previous.runName ? ` · ${previous.runName}` : ''}`
}

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
        badge: describeChange(item.change),
        previousText: props.changes ? previousText(item) : '',
      }
    })
})

const emptyText = computed(() => {
  if (statusFilter.value === 'incidents') return 'Падений нет — все тесты прошли.'
  if (statusFilter.value === 'changes') return 'По сравнению с прошлыми запусками ничего не изменилось.'
  return 'Здесь нет результатов.'
})

function openTest(testKey: string | null | undefined) {
  if (testKey) emit('openTest', testKey)
}
</script>

<template>
  <div class="results">
    <div v-if="changes" class="results-changes" aria-label="Сравнение с предыдущими запусками">
      <span class="results-changes-title">По сравнению с прошлым запуском</span>
      <span v-if="!visibleChangeStats.length" class="results-changes-empty">без изменений</span>
      <button
        v-for="stat in visibleChangeStats"
        :key="stat.key"
        type="button"
        class="change-stat"
        :class="`change-stat--${stat.key}`"
        @click="statusFilter = STAT_FILTER[stat.key] ?? 'changes'"
      >
        <strong>{{ stat.count }}</strong>
        {{ stat.label }}
      </button>
    </div>

    <div class="results-toolbar">
      <div class="results-segmented" role="group" aria-label="Какие результаты показывать">
        <button type="button" :aria-pressed="statusFilter === 'incidents'" @click="statusFilter = 'incidents'">
          Падения<span v-if="incidentsCount !== undefined" class="results-count">{{ incidentsCount }}</span>
        </button>
        <button
          v-if="changes"
          type="button"
          :aria-pressed="statusFilter === 'changes'"
          @click="statusFilter = 'changes'"
        >
          Изменения<span class="results-count results-count--neutral">{{ changesCount }}</span>
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
    <p v-else-if="!items.length" class="results-state">{{ emptyText }}</p>
    <p v-else-if="!rows.length" class="results-state">Ничего не найдено.</p>

    <ul v-else class="results-list" :aria-busy="loading">
      <li v-for="row in rows" :key="row.id" class="result" :class="`result--${row.tone}`">
        <details v-if="row.message" class="result-details">
          <summary class="result-row">
            <span class="result-icon" aria-hidden="true"></span>
            <span class="result-main">
              <span class="result-title-line">
                <span class="result-title">{{ row.title }}</span>
                <span
                  v-if="row.badge"
                  class="change-badge"
                  :class="`change-badge--${row.badge.tone}`"
                  :title="row.previousText"
                >
                  {{ row.badge.label }}
                </span>
              </span>
              <span v-if="row.subtitle" class="result-subtitle">{{ row.subtitle }}</span>
              <span class="result-first-line">{{ row.firstLine }}</span>
            </span>
            <span class="status-pill" :class="`status-pill--${row.tone}`">{{ row.status }}</span>
            <span class="result-duration">{{ row.durationText }}</span>
            <button
              v-if="row.testKey"
              type="button"
              class="result-history"
              :class="{ 'is-loading': openingTestKey === row.testKey }"
              :aria-label="`История теста ${row.title}`"
              title="История теста"
              @click.stop.prevent="openTest(row.testKey)"
            >
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5M12 7v5l3 2" /></svg>
            </button>
          </summary>
          <div class="result-expanded">
            <pre class="result-message">{{ row.message }}</pre>
            <div class="result-footer">
              <span v-if="row.previousText" class="result-previous">{{ row.previousText }}</span>
              <RouterLink
                v-if="row.signature"
                class="signature-chip"
                :to="{ name: 'dashboard', query: { signature: row.signature } }"
                title="Открыть дашборд с этой сигнатурой"
              >
                <span class="signature-chip-label">Сигнатура</span>
                <span class="signature-chip-text">{{ row.signature }}</span>
                <span aria-hidden="true">→</span>
              </RouterLink>
            </div>
          </div>
        </details>
        <div v-else class="result-row">
          <span class="result-icon" aria-hidden="true"></span>
          <span class="result-main">
            <span class="result-title-line">
              <span class="result-title">{{ row.title }}</span>
              <span
                v-if="row.badge"
                class="change-badge"
                :class="`change-badge--${row.badge.tone}`"
                :title="row.previousText"
              >
                {{ row.badge.label }}
              </span>
            </span>
            <span v-if="row.subtitle" class="result-subtitle">{{ row.subtitle }}</span>
          </span>
          <span class="status-pill" :class="`status-pill--${row.tone}`">{{ row.status }}</span>
          <span class="result-duration">{{ row.durationText }}</span>
          <button
            v-if="row.testKey"
            type="button"
            class="result-history"
            :class="{ 'is-loading': openingTestKey === row.testKey }"
            :aria-label="`История теста ${row.title}`"
            title="История теста"
            @click="openTest(row.testKey)"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5M12 7v5l3 2" /></svg>
          </button>
        </div>
      </li>
    </ul>
    <p v-if="total > items.length" class="results-more muted">Показаны первые {{ items.length }} из {{ total }}</p>
  </div>
</template>

<style scoped src="../../../assets/style/components/results/TestResultList.css"></style>
