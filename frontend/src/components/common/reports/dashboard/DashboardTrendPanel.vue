<script setup lang="ts">
import { computed } from 'vue'

import { parseRunLabel } from '../../../../utils/reports'
import type { TrendPoint } from './types'

const props = defineProps<{
  trendPoints: TrendPoint[]
}>()

const emit = defineEmits<{
  openReport: [id: string]
  openRun: [uuid: string]
}>()

function open(point: TrendPoint) {
  if (point.reportId) emit('openReport', point.reportId)
  else emit('openRun', point.key)
}

const columns = computed(() =>
  props.trendPoints.map((point, index) => {
    const total = point.total || 1
    const other = Math.max(0, point.total - point.passed - point.failed - point.broken)
    const share = (value: number) => `${(value / total) * 100}%`
    const { day, time } = parseRunLabel(point.label)
    return {
      ...point,
      day,
      time,
      isLatest: index === props.trendPoints.length - 1,
      tone: point.passRate < 70 ? 'failed' : point.passRate < 90 ? 'broken' : 'ok',
      segments: [
        { key: 'other', height: share(other) },
        { key: 'broken', height: share(point.broken) },
        { key: 'failed', height: share(point.failed) },
        { key: 'passed', height: share(point.passed) },
      ].filter((segment) => segment.height !== '0%'),
    }
  }),
)

const gridStyle = computed(() => ({
  gridTemplateColumns: `repeat(${Math.max(columns.value.length, 1)}, minmax(0, 1fr))`,
}))
</script>

<template>
  <article class="panel panel--trend">
    <header class="panel-header">
      <div>
        <h2 class="panel-title">Тренд прогонов</h2>
        <p class="panel-hint">Последние {{ trendPoints.length }} прогонов · доля статусов</p>
      </div>
      <ul class="chart-legend" aria-label="Легенда">
        <li><span class="legend-dot legend-dot--passed"></span>Пройдено</li>
        <li><span class="legend-dot legend-dot--failed"></span>Сбой</li>
        <li><span class="legend-dot legend-dot--broken"></span>Сломано</li>
        <li><span class="legend-dot legend-dot--other"></span>Прочее</li>
      </ul>
    </header>

    <div class="trend-chart" :style="gridStyle">
      <button
        v-for="column in columns"
        :key="column.key"
        type="button"
        class="trend-column trend-column--link"
        :class="{ 'trend-column--latest': column.isLatest }"
        :title="`${column.label} — открыть ${column.reportId ? 'Allure-отчёт' : 'прогон'}`"
        :aria-label="`${column.label}: пройдено ${column.passRate}%, ${column.total} тестов`"
        @click="open(column)"
      >
        <span class="trend-rate" :class="`trend-rate--${column.tone}`">{{ column.passRate }}%</span>
        <span class="trend-bar">
          <span
            v-for="segment in column.segments"
            :key="segment.key"
            class="trend-segment"
            :class="`trend-segment--${segment.key}`"
            :style="{ height: segment.height }"
          ></span>
        </span>
        <span class="trend-axis">
          <strong>{{ column.day }}</strong>
          <span v-if="column.time">{{ column.time }}</span>
          <span>{{ column.total }} т.</span>
        </span>
      </button>
    </div>
  </article>
</template>
