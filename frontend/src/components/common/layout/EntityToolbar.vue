<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, useId, useSlots, watch } from 'vue'
import type { RouteLocationRaw } from 'vue-router'

export type ToolbarCount = { label: string; value: number; dot?: 'passed' | 'failed' | 'broken' | 'other' }
export type ToolbarMeta = { label: string; value: string; mono?: boolean; title?: string }
export type ToolbarLink = { label: string; to?: RouteLocationRaw; href?: string }
export type ToolbarMenuItem = { label: string; icon: 'download' | 'delete'; danger?: boolean; action: () => void }

/**
 * Compact header of a report or a run: optional tabs, date and time, author,
 * status, pass rate with a status bar, an info popover with counters and
 * metadata, an optional link and an optional "more" menu.
 */
const props = defineProps<{
  title: string
  /** "28.09 · 05:00" when the name could be parsed; the full title is the fallback. */
  dateTime?: string | null
  user?: string | null
  status: string
  tone: string
  passRate?: number | null
  shares?: { passed: string; failed: string; broken: string } | null
  counts: ToolbarCount[]
  meta: ToolbarMeta[]
  link?: ToolbarLink | null
  menu?: ToolbarMenuItem[]
  /** Popovers close when this changes (another report or run is selected). */
  resetKey?: string | null
}>()

const slots = useSlots()
const infoId = useId()
const root = ref<HTMLElement | null>(null)
const openMenu = ref<'info' | 'more' | null>(null)

const rateTone = (rate: number) => (rate < 70 ? 'failed' : rate < 90 ? 'broken' : 'ok')

function toggle(menu: 'info' | 'more') {
  openMenu.value = openMenu.value === menu ? null : menu
}

function close() {
  openMenu.value = null
}

function runItem(item: ToolbarMenuItem) {
  close()
  item.action()
}

function onDocumentClick(event: MouseEvent) {
  if (openMenu.value && root.value && !root.value.contains(event.target as Node)) close()
}

function onKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') close()
}

onMounted(() => {
  document.addEventListener('click', onDocumentClick)
  document.addEventListener('keydown', onKeydown)
  // Clicks inside an embedded iframe never reach the document; the window loses focus instead.
  window.addEventListener('blur', close)
})

onBeforeUnmount(() => {
  document.removeEventListener('click', onDocumentClick)
  document.removeEventListener('keydown', onKeydown)
  window.removeEventListener('blur', close)
})

watch(() => props.resetKey, close)
</script>

<template>
  <header ref="root" class="toolbar">
    <template v-if="slots.tabs">
      <slot name="tabs" />
      <span class="toolbar-divider" aria-hidden="true"></span>
    </template>

    <div class="toolbar-title" :title="title">
      <h2 v-if="dateTime" class="toolbar-title-date">{{ dateTime }}</h2>
      <h2 v-else class="toolbar-title-text">{{ title }}</h2>
      <span v-if="user" class="toolbar-title-user">{{ user }}</span>
      <span class="status-pill" :class="`status-pill--${tone}`">{{ status }}</span>
    </div>

    <div class="toolbar-summary">
      <template v-if="passRate !== null && passRate !== undefined">
        <strong class="toolbar-rate" :class="`rate--${rateTone(passRate)}`" title="Pass rate">{{ passRate }}%</strong>
        <span v-if="shares" class="stack-bar toolbar-bar" aria-hidden="true">
          <span class="stack-bar-seg stack-bar-seg--passed" :style="{ width: shares.passed }"></span>
          <span class="stack-bar-seg stack-bar-seg--failed" :style="{ width: shares.failed }"></span>
          <span class="stack-bar-seg stack-bar-seg--broken" :style="{ width: shares.broken }"></span>
        </span>
      </template>

      <div class="toolbar-actions">
        <button
          type="button"
          class="icon-button"
          aria-label="Подробнее"
          title="Подробнее"
          :aria-expanded="openMenu === 'info'"
          :aria-controls="infoId"
          @click="toggle('info')"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9" /><path d="M12 11v5M12 8v.5" /></svg>
        </button>
        <template v-if="link">
          <RouterLink v-if="link.to" class="icon-button" :to="link.to" :aria-label="link.label" :title="link.label">
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M14 4h6v6M20 4l-9 9" />
              <path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" />
            </svg>
          </RouterLink>
          <a
            v-else-if="link.href"
            class="icon-button"
            :href="link.href"
            target="_blank"
            rel="noopener"
            :aria-label="link.label"
            :title="link.label"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M14 4h6v6M20 4l-9 9" />
              <path d="M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5" />
            </svg>
          </a>
        </template>
        <button
          v-if="menu?.length"
          type="button"
          class="icon-button"
          aria-label="Ещё действия"
          :title="menu.map((item) => item.label).join(', ')"
          aria-haspopup="menu"
          :aria-expanded="openMenu === 'more'"
          @click="toggle('more')"
        >
          <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12h.5M12 12h.5M19 12h.5" /></svg>
        </button>
      </div>
    </div>

    <div v-if="openMenu === 'info'" :id="infoId" class="toolbar-popover toolbar-info" role="dialog" aria-label="Подробнее">
      <div v-if="counts.length" class="toolbar-counts">
        <span v-for="count in counts" :key="count.label">
          <i v-if="count.dot" class="legend-dot" :class="`legend-dot--${count.dot}`"></i>{{ count.label }}
          <b>{{ count.value }}</b>
        </span>
      </div>
      <dl class="toolbar-meta">
        <template v-for="item in meta" :key="item.label">
          <dt>{{ item.label }}</dt>
          <dd :class="{ mono: item.mono }" :title="item.title">{{ item.value }}</dd>
        </template>
      </dl>
    </div>

    <div v-if="openMenu === 'more' && menu?.length" class="toolbar-popover toolbar-menu" role="menu">
      <button
        v-for="item in menu"
        :key="item.label"
        type="button"
        role="menuitem"
        :class="{ 'toolbar-menu-danger': item.danger }"
        @click="runItem(item)"
      >
        <svg v-if="item.icon === 'download'" viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 4v12M7 11l5 5 5-5M4 20h16" />
        </svg>
        <svg v-else viewBox="0 0 24 24" aria-hidden="true"><path d="M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13" /></svg>
        {{ item.label }}
      </button>
    </div>
  </header>
</template>

<style scoped src="../../../assets/style/components/common/EntityToolbar.css"></style>
