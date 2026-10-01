<script setup lang="ts">
import { computed } from 'vue'

import { splitTestName, statusTone } from '../../../../utils/reports'
import type { StabilityBucketKey, UnstableTest } from './types'

const props = defineProps<{
  topUnstableTests: UnstableTest[]
  flakyCount: number
}>()

const emit = defineEmits<{
  selectTest: [key: string]
  openBucket: [bucket: StabilityBucketKey]
}>()

const rows = computed(() =>
  props.topUnstableTests.map((item) => ({
    ...item,
    ...splitTestName(item.name),
    lastTone: statusTone(item.lastStatus),
    rateTone: item.stability < 70 ? 'failed' : item.stability < 90 ? 'broken' : 'ok',
    dots: (item.recentStatuses ?? []).map((status, index) => ({ key: index, status, tone: statusTone(status) })),
  })),
)
</script>

<template>
  <article class="panel panel--unstable">
    <header class="panel-header">
      <div>
        <h2 class="panel-title">Самые нестабильные тесты</h2>
        <p class="panel-hint">История запусков: последний справа · нажми на тест, чтобы открыть детали</p>
      </div>
      <button v-if="flakyCount" type="button" class="panel-link" @click="emit('openBucket', 'flaky')">
        Все {{ flakyCount }} →
      </button>
    </header>

    <div class="data-table">
      <div class="data-table-head unstable-grid" aria-hidden="true">
        <span>Тест</span>
        <span>История</span>
        <span class="align-end">Pass</span>
        <span>Последний</span>
      </div>
      <button
        v-for="row in rows"
        :key="row.key"
        type="button"
        class="data-table-row unstable-grid"
       
        @click="emit('selectTest', row.key)"
      >
        <span class="test-name" :title="row.name">
          <span v-if="row.module" class="test-name-module">{{ row.module }}</span>
          <span class="test-name-method">{{ row.method }}</span>
        </span>
        <span class="run-dots">
          <span
            v-for="dot in row.dots"
            :key="dot.key"
            class="run-dot"
            :class="`run-dot--${dot.tone}`"
            :title="dot.status"
          ></span>
          <span v-if="!row.dots.length" class="muted">{{ row.passedRuns }}/{{ row.totalRuns }} пройдено</span>
        </span>
        <span class="mono-strong align-end" :class="`rate--${row.rateTone}`">{{ row.stability }}%</span>
        <span>
          <span class="status-pill" :class="`status-pill--${row.lastTone}`">{{ row.lastStatus }}</span>
        </span>
      </button>
    </div>
  </article>
</template>
