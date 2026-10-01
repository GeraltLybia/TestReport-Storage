<script setup lang="ts">
import { computed } from 'vue'

import type { TagHealth } from './types'

const props = defineProps<{
  activeTags: string[]
  tagHealth: TagHealth[]
}>()

const emit = defineEmits<{
  toggleTag: [tag: string]
}>()

const rows = computed(() =>
  props.tagHealth.map((item) => {
    const share = (value: number) => `${item.total ? (value / item.total) * 100 : 0}%`
    return {
      ...item,
      passed: share(item.passedRuns),
      failed: share(item.failedRuns),
      broken: share(item.brokenRuns),
      rateTone: item.healthyRate < 70 ? 'failed' : item.healthyRate < 90 ? 'broken' : 'ok',
      active: props.activeTags.includes(item.tag),
    }
  }),
)
</script>

<template>
  <article class="panel panel--tags">
    <header class="panel-header">
      <div>
        <h2 class="panel-title">Состояние по тегам</h2>
        <p class="panel-hint">Больше всего инцидентов сверху · нажми на тег, чтобы включить фильтр</p>
      </div>
    </header>

    <p v-if="!rows.length" class="panel-empty">Тегов нет.</p>
    <div v-else class="tag-list">
      <button
        v-for="row in rows"
        :key="row.tag"
        type="button"
        class="tag-row"
        :class="{ 'tag-row--active': row.active }"
        :aria-pressed="row.active"
        @click="emit('toggleTag', row.tag)"
      >
        <span class="tag-row-name">{{ row.tag }}</span>
        <span class="mono-strong align-end" :class="`rate--${row.rateTone}`">{{ row.healthyRate }}%</span>
        <span class="stack-bar">
          <span class="stack-bar-seg stack-bar-seg--passed" :style="{ width: row.passed }"></span>
          <span class="stack-bar-seg stack-bar-seg--failed" :style="{ width: row.failed }"></span>
          <span class="stack-bar-seg stack-bar-seg--broken" :style="{ width: row.broken }"></span>
        </span>
        <span class="muted align-end">{{ row.total }} прог.</span>
        <span class="tag-row-meta">
          пройдено {{ row.passedRuns }} · сбой {{ row.failedRuns }} · сломано {{ row.brokenRuns }}
        </span>
      </button>
    </div>
  </article>
</template>
