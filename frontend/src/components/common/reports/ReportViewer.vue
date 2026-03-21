<script setup lang="ts">
defineProps<{
  sidebarVisible: boolean
  viewerSrc: string | null
}>()

const emit = defineEmits<{
  showSidebar: []
}>()
</script>

<template>
  <section class="viewer">
    <button
      v-if="!sidebarVisible"
      type="button"
      class="viewer-toggle"
      @click="emit('showSidebar')"
    >
      Показать список отчетов
    </button>
    <iframe
      v-if="viewerSrc"
      :key="viewerSrc"
      :src="viewerSrc"
      title="Allure report"
      class="viewer-frame"
    />
    <div v-else class="viewer-placeholder">
      <h2>Выберите отчет</h2>
      <p>Список доступных отчетов находится слева.</p>
    </div>
  </section>
</template>

<style scoped src="../../../assets/style/components/reports/ReportViewer.css"></style>
