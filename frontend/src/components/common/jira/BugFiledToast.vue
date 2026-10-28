<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'

import { pluralRu } from '../../../utils/reports'
import type { BugFiled } from './BugCreateDialog.vue'

const props = defineProps<{ event: BugFiled }>()
const emit = defineEmits<{ close: [] }>()

const HIDE_AFTER_MS = 12000
const copied = ref(false)
let timer: ReturnType<typeof setTimeout> | null = null

const key = computed(() => props.event.result.key)
const title = computed(() => (props.event.type === 'issue' ? `Баг ${key.value} создан` : `Комментарий добавлен в ${key.value}`))
const details = computed(() => {
  const result = props.event.result
  const parts: string[] = []
  if (props.event.type === 'issue') {
    const { steps, logLines } = props.event.result
    parts.push(`${steps} ${pluralRu(steps, ['шаг', 'шага', 'шагов'])}`)
    // in the «calls» mode the backend counts requests, in the «full» mode log lines
    if (logLines && props.event.logMode === 'calls') {
      parts.push(`${logLines} ${pluralRu(logLines, ['запрос', 'запроса', 'запросов'])}`)
    } else if (logLines) {
      parts.push(`${logLines} ${pluralRu(logLines, ['строка', 'строки', 'строк'])} лога`)
    }
  }
  parts.push(...result.attachments)
  return parts.join(' · ')
})

async function copyKey() {
  try {
    await navigator.clipboard.writeText(key.value)
    copied.value = true
  } catch {
    copied.value = false
  }
}

function pause() {
  if (timer) clearTimeout(timer)
  timer = null
}

function resume() {
  pause()
  timer = setTimeout(() => emit('close'), HIDE_AFTER_MS)
}

onMounted(resume)
onBeforeUnmount(pause)
</script>

<template>
  <Teleport to="body">
    <div class="bug-toast" role="status" @mouseenter="pause" @mouseleave="resume" @focusin="pause" @focusout="resume">
      <span class="bug-toast-icon" aria-hidden="true">
        <svg viewBox="0 0 24 24"><path d="M5 12l5 5 9-10" /></svg>
      </span>
      <div class="bug-toast-body">
        <b>{{ title }}</b>
        <span v-if="event.type === 'issue'" class="bug-toast-summary">{{ event.result.summary }}</span>
        <span v-if="details" class="bug-toast-details">{{ details }}</span>
        <span v-for="warning in event.result.warnings" :key="warning" class="bug-toast-warning">{{ warning }}</span>
        <span class="bug-toast-actions">
          <a :href="event.result.url" target="_blank" rel="noopener">Открыть в Jira ↗</a>
          <button type="button" @click="copyKey">{{ copied ? 'Скопировано' : 'Скопировать ключ' }}</button>
        </span>
      </div>
      <button type="button" class="bug-toast-close" aria-label="Закрыть" @click="emit('close')">×</button>
    </div>
  </Teleport>
</template>

<style scoped>
.bug-toast {
  position: fixed;
  right: 1.875rem;
  bottom: 1.875rem;
  z-index: 70;
  display: flex;
  gap: 0.75rem;
  align-items: flex-start;
  width: min(23.75rem, calc(100vw - 2rem));
  padding: 0.875rem 1rem;
  border: 1px solid var(--border);
  border-radius: 14px;
  background: var(--surface);
  color: var(--text);
  box-shadow: var(--shadow-pop);
  animation: bug-toast-in var(--dur-base) var(--ease-apple) both;
}

.bug-toast-icon {
  width: 1.875rem;
  height: 1.875rem;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border-radius: 9px;
  background: var(--success-soft);
  color: var(--success);
}

.bug-toast-icon svg {
  width: 1rem;
  height: 1rem;
  fill: none;
  stroke: currentColor;
  stroke-width: 2.4;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.bug-toast-body {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-width: 0;
  flex: 1;
}

.bug-toast-summary {
  font-size: 0.82rem;
  color: var(--text-2);
}

.bug-toast-details {
  font-size: 0.78rem;
  color: var(--text-3);
}

.bug-toast-warning {
  font-size: 0.78rem;
  color: var(--warning);
}

.bug-toast-actions {
  display: flex;
  gap: 0.875rem;
  margin-top: 0.25rem;
  font-size: 0.82rem;
  font-weight: 600;
}

.bug-toast-actions a {
  color: var(--accent-strong);
  text-decoration: none;
}

.bug-toast-actions button,
.bug-toast-close {
  padding: 0;
  border: 0;
  background: none;
  color: var(--text-2);
  font: inherit;
  cursor: pointer;
}

.bug-toast-close {
  font-size: 1.1rem;
  line-height: 1;
  color: var(--text-3);
}

@keyframes bug-toast-in {
  from {
    opacity: 0;
    transform: translateY(12px);
  }
}

@media (prefers-reduced-motion: reduce) {
  .bug-toast {
    animation: none;
  }
}
</style>
