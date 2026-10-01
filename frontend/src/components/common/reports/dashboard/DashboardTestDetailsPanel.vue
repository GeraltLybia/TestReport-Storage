<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref } from 'vue'

import { formatDate, formatShortDuration, splitTestName, statusTone } from '../../../../utils/reports'
import type { SelectedTestDetails } from './types'

const props = defineProps<{
  selectedTestDetails: SelectedTestDetails
  normalizeStatus: (value: string | undefined) => string
}>()

const emit = defineEmits<{
  close: []
}>()

const closeButton = ref<HTMLButtonElement | null>(null)

const title = computed(() => splitTestName(props.selectedTestDetails.name))
const lastTone = computed(() => statusTone(props.selectedTestDetails.lastStatus))
const passRate = computed(() => {
  const { totalRuns, incidents } = props.selectedTestDetails
  return totalRuns ? Math.round(((totalRuns - incidents) / totalRuns) * 100) : 0
})

const entries = computed(() =>
  props.selectedTestDetails.history.map((entry, index) => {
    const status = props.normalizeStatus(entry.status)
    return {
      key: `${index}-${entry.start ?? 0}`,
      status,
      tone: statusTone(status),
      date: entry.start ? formatDate(new Date(entry.start).toISOString()) : '-',
      duration: formatShortDuration(entry.duration),
      durationMs: entry.duration ?? 0,
      environment: entry.environment || 'unknown',
      message: entry.message?.split('\n').slice(0, 6).join('\n').trim() ?? '',
    }
  }),
)

// History comes newest first; the chart reads left-to-right, oldest first.
const bars = computed(() => {
  const ordered = [...entries.value].reverse()
  const max = Math.max(1, ...ordered.map((entry) => entry.durationMs))
  return ordered.map((entry) => ({ ...entry, height: `${Math.max(4, (entry.durationMs / max) * 100)}%` }))
})

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') emit('close')
}

onMounted(() => {
  document.addEventListener('keydown', onKeydown)
  void nextTick(() => closeButton.value?.focus())
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <Teleport to="body">
    <div class="drawer-backdrop" @click.self="emit('close')">
      <aside class="drawer" role="dialog" aria-modal="true" :aria-label="`Детали теста ${title.method}`">
        <header class="drawer-header">
          <div class="drawer-header-top">
            <span class="drawer-kicker">Детали теста</span>
            <button ref="closeButton" type="button" class="icon-button" aria-label="Закрыть" @click="emit('close')">
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 6l12 12M18 6L6 18" /></svg>
            </button>
          </div>
          <span v-if="title.module" class="drawer-module">{{ title.module }}</span>
          <h2 class="drawer-title">{{ title.method }}</h2>
        </header>

        <div class="drawer-body">
          <div class="drawer-stats">
            <div class="mini-stat">
              <span>Последний</span>
              <span class="status-pill" :class="`status-pill--${lastTone}`">{{ selectedTestDetails.lastStatus }}</span>
            </div>
            <div class="mini-stat">
              <span>Pass rate</span>
              <strong :class="`rate--${passRate < 70 ? 'failed' : passRate < 90 ? 'broken' : 'ok'}`">{{ passRate }}%</strong>
            </div>
            <div class="mini-stat">
              <span>Прогонов</span>
              <strong>{{ selectedTestDetails.totalRuns }}</strong>
            </div>
            <div class="mini-stat">
              <span>Инцидентов</span>
              <strong>{{ selectedTestDetails.incidents }}</strong>
            </div>
          </div>

          <section v-if="bars.length" class="drawer-section" aria-label="Длительность по прогонам">
            <h3>Длительность и статус</h3>
            <div class="duration-chart" :style="{ gridTemplateColumns: `repeat(${bars.length}, minmax(0, 1fr))` }">
              <div v-for="bar in bars" :key="bar.key" class="duration-column" :title="`${bar.date} · ${bar.status}`">
                <span class="duration-value">{{ bar.duration }}</span>
                <span class="duration-bar" :class="`duration-bar--${bar.tone}`" :style="{ height: bar.height }"></span>
              </div>
            </div>
          </section>

          <section class="drawer-section" aria-label="История запусков">
            <h3>История запусков</h3>
            <p v-if="selectedTestDetails.totalRuns > entries.length" class="panel-hint">
              Показаны последние {{ entries.length }} из {{ selectedTestDetails.totalRuns }}
            </p>
            <article v-for="entry in entries" :key="entry.key" class="history-card">
              <div class="history-card-top">
                <span class="status-pill" :class="`status-pill--${entry.tone}`">{{ entry.status }}</span>
                <span class="history-date">{{ entry.date }}</span>
                <span class="muted">{{ entry.environment }}</span>
                <span class="history-duration">{{ entry.duration }}</span>
              </div>
              <pre v-if="entry.message && entry.tone !== 'passed'" class="history-message" :class="`history-message--${entry.tone}`">{{ entry.message }}</pre>
            </article>
          </section>
        </div>
      </aside>
    </div>
  </Teleport>
</template>
