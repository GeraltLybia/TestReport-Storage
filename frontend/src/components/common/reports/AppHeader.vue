<script setup lang="ts">
type Theme = 'dark' | 'light'

defineProps<{
  sidebarVisible: boolean
  theme: Theme
  uploading: boolean
}>()

const emit = defineEmits<{
  'toggle-sidebar': []
  'toggle-theme': []
  'upload-report': [event: Event]
}>()
</script>

<template>
  <header class="app-header">
    <div>
      <h1>Allure Reports</h1>
      <p class="app-subtitle">Хранилище и просмотр отчетов тестов</p>
    </div>
    <div class="header-actions">
      <button
        class="text-button header-toggle"
        type="button"
        @click="emit('toggle-sidebar')"
      >
        {{ sidebarVisible ? 'Скрыть список' : 'Показать список' }}
      </button>
      <label class="theme-toggle" :title="theme === 'dark' ? 'Тёмная тема' : 'Светлая тема'">
        <input
          type="checkbox"
          :checked="theme === 'light'"
          @change="emit('toggle-theme')"
        />
        <span class="theme-toggle-track">
          <span class="theme-toggle-thumb" />
        </span>
        <span class="theme-toggle-label">
          {{ theme === 'dark' ? 'Тёмная' : 'Светлая' }}
        </span>
      </label>
      <label class="upload-button">
        <span>{{ uploading ? 'Загрузка...' : 'Загрузить отчет (ZIP)' }}</span>
        <input
          type="file"
          accept=".zip"
          :disabled="uploading"
          @change="emit('upload-report', $event)"
        />
      </label>
    </div>
  </header>
</template>

<style scoped src="../../../assets/style/components/reports/AppHeader.css"></style>
