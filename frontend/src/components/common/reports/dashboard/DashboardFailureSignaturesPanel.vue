<script setup lang="ts">
import { computed } from 'vue'

import type { FailureSignature } from './types'

const props = defineProps<{
  activeSignature: string
  failureSignatures: FailureSignature[]
}>()

const emit = defineEmits<{
  toggleSignature: [signature: string]
}>()

const rows = computed(() => {
  const max = Math.max(1, ...props.failureSignatures.map((item) => item.count))
  return props.failureSignatures.map((item) => {
    const separator = item.signature.indexOf(': ')
    const fullType = separator > 0 ? item.signature.slice(0, separator) : ''
    return {
      ...item,
      type: fullType ? (fullType.split('.').pop() ?? fullType) : 'Ошибка',
      message: separator > 0 ? item.signature.slice(separator + 2) : item.signature,
      width: `${Math.round((item.count / max) * 100)}%`,
      active: props.activeSignature === item.signature,
    }
  })
})
</script>

<template>
  <article class="panel panel--signatures">
    <header class="panel-header">
      <div>
        <h2 class="panel-title">Сигнатуры сбоев</h2>
        <p class="panel-hint">Нажми, чтобы отфильтровать дашборд</p>
      </div>
    </header>

    <p v-if="!rows.length" class="panel-empty">Сбоев нет.</p>
    <div v-else class="signature-list">
      <button
        v-for="row in rows"
        :key="row.signature"
        type="button"
        class="signature-row"
        :class="{ 'signature-row--active': row.active }"
        :aria-pressed="row.active"
        :title="row.signature"
        @click="emit('toggleSignature', row.signature)"
      >
        <span class="signature-top">
          <span class="signature-type">{{ row.type }}</span>
          <span class="mono-strong">{{ row.count }}</span>
        </span>
        <span class="signature-message">{{ row.message }}</span>
        <span class="meter"><span class="meter-fill" :style="{ width: row.width }"></span></span>
      </button>
    </div>
  </article>
</template>
