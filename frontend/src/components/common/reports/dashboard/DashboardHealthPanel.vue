<script setup lang="ts">
import { computed } from 'vue'

import type { AggregateStats, StabilityBucketKey, StabilitySummary } from './types'

const props = defineProps<{
  aggregateStats: AggregateStats
  passRate: number
  stabilitySummary: StabilitySummary
}>()

const emit = defineEmits<{
  openBucket: [bucket: StabilityBucketKey]
}>()

const incidents = computed(() => props.aggregateStats.failed + props.aggregateStats.broken)

const otherResults = computed(() => {
  const { total, passed, failed, broken } = props.aggregateStats
  return Math.max(0, total - passed - failed - broken)
})

const ringStyle = computed(() => {
  const { total, passed, failed, broken } = props.aggregateStats
  if (!total) return { background: 'var(--track)' }
  const p = (passed / total) * 100
  const f = p + (failed / total) * 100
  const b = f + (broken / total) * 100
  return {
    background: `conic-gradient(var(--bar-passed) 0 ${p}%, var(--bar-failed) ${p}% ${f}%, var(--bar-broken) ${f}% ${b}%, var(--bar-skipped) ${b}% 100%)`,
  }
})
</script>

<template>
  <article class="panel panel--health">
    <header class="panel-header">
      <div>
        <h2 class="panel-title">Общая стабильность</h2>
        <p class="panel-hint">{{ aggregateStats.total }} результатов по всем прогонам</p>
      </div>
    </header>

    <div class="health-layout">
      <div class="health-ring" :style="ringStyle">
        <div class="health-ring-center">
          <strong>{{ passRate }}%</strong>
          <span>пройдено</span>
        </div>
      </div>

      <dl class="health-legend">
        <div class="legend-row">
          <dt><span class="legend-dot legend-dot--passed"></span>Пройдено</dt>
          <dd>{{ aggregateStats.passed }}</dd>
        </div>
        <div class="legend-row">
          <dt><span class="legend-dot legend-dot--failed"></span>Сбой</dt>
          <dd>{{ aggregateStats.failed }}</dd>
        </div>
        <div class="legend-row">
          <dt><span class="legend-dot legend-dot--broken"></span>Сломано</dt>
          <dd>{{ aggregateStats.broken }}</dd>
        </div>
        <div class="legend-row">
          <dt><span class="legend-dot legend-dot--other"></span>Пропущено и прочее</dt>
          <dd>{{ otherResults }}</dd>
        </div>
      </dl>
    </div>

    <div class="health-buckets">
      <button type="button" class="health-bucket" @click="emit('openBucket', 'alwaysPassed')">
        <span>Всегда проходят</span>
        <strong class="tone-passed">{{ stabilitySummary.alwaysPassed }}</strong>
      </button>
      <button type="button" class="health-bucket" @click="emit('openBucket', 'alwaysFailed')">
        <span>Всегда падают</span>
        <strong class="tone-failed">{{ stabilitySummary.alwaysFailed }}</strong>
      </button>
      <button type="button" class="health-bucket" @click="emit('openBucket', 'incidents')">
        <span>Инциденты</span>
        <strong class="tone-broken">{{ incidents }}</strong>
      </button>
    </div>
  </article>
</template>
