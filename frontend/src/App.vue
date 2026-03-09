<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'

import { useReports } from './modules/reports/useReports'

const {
  downloadHistory,
  error,
  formatDate,
  formatDuration,
  formatSize,
  getReportTitle,
  handleDeleteReport,
  handleDownloadReport,
  handleHistoryUpload,
  handleUploadReport,
  historyInfo,
  loading,
  loadReports,
  reports,
  selectedReportId,
  sidebarVisible,
  uploading,
  viewerSrc,
} = useReports()

type Theme = 'dark' | 'light'
const theme = ref<Theme>('dark')

function applyTheme(value: Theme) {
  document.documentElement.setAttribute('data-theme', value)
}

function toggleTheme() {
  theme.value = theme.value === 'dark' ? 'light' : 'dark'
}

onMounted(() => {
  const saved = localStorage.getItem('theme')
  if (saved === 'dark' || saved === 'light') {
    theme.value = saved
  }
  applyTheme(theme.value)
})

watch(theme, (value) => {
  applyTheme(value)
  localStorage.setItem('theme', value)
})
</script>

<template>
  <div class="app-root">
    <header class="app-header">
      <div>
        <h1>Allure Reports</h1>
        <p class="app-subtitle">Хранилище и просмотр отчетов тестов</p>
      </div>
      <div class="header-actions">
        <button
          class="text-button header-toggle"
          type="button"
          @click="sidebarVisible = !sidebarVisible"
        >
          {{ sidebarVisible ? 'Скрыть список' : 'Показать список' }}
        </button>
        <label class="theme-toggle" :title="theme === 'dark' ? 'Тёмная тема' : 'Светлая тема'">
          <input
            type="checkbox"
            :checked="theme === 'light'"
            @change="toggleTheme"
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
            @change="handleUploadReport"
          />
        </label>
      </div>
    </header>

    <div v-if="error" class="app-error">
      {{ error }}
    </div>

    <main class="app-main" :class="{ 'app-main--no-sidebar': !sidebarVisible }">
      <section v-if="sidebarVisible" class="sidebar">
        <div class="sidebar-header">
          <div class="sidebar-title">
            <span>Отчеты</span>
            <span v-if="loading" class="chip">Загрузка…</span>
          </div>
          <button class="text-button" type="button" @click="loadReports">
            Обновить
          </button>
        </div>

        <div v-if="!reports.length && !loading" class="empty-state">
          <p>Пока нет ни одного отчета.</p>
          <p>Загрузите ZIP c Allure отчетом, чтобы начать.</p>
        </div>

        <ul class="report-list">
          <li
            v-for="report in reports"
            :key="report.id"
            class="report-item"
            :class="{ 'report-item--active': report.id === selectedReportId }"
            @click="selectedReportId = report.id"
          >
            <div class="report-main">
              <div class="report-name">
                {{ getReportTitle(report) }}
              </div>
              <div class="report-meta">
                <span>{{ formatDate(report.created_at) }}</span>
                <span>·</span>
                <span>{{ formatSize(report.size) }}</span>
                <span>·</span>
                <span>Duration: {{ formatDuration(report.duration) }}</span>
                <span>·</span>
                <span class="report-id-short">
                  {{ report.id.slice(0, 8) }}…
                </span>
              </div>
              <div v-if="report.status" class="report-status">
                <span
                  class="stat-chip"
                  :class="`status-chip status-chip--${report.status.toLowerCase()}`"
                >
                  Status: {{ report.status }}
                </span>
              </div>
              <div v-if="report.stats" class="report-stats">
                <span class="stat-chip stat-chip--failed">
                  Failed: {{ report.stats.failed }}
                </span>
                <span class="stat-chip stat-chip--passed">
                  Passed: {{ report.stats.passed }}
                </span>
                <span class="stat-chip stat-chip--flaky">
                  Flaky: {{ report.stats.flaky }}
                </span>
                <span class="stat-chip stat-chip--broken">
                  Broken: {{ report.stats.broken }}
                </span>
                <span class="stat-chip">
                  Total: {{ report.stats.total }}
                </span>
              </div>
            </div>
            <div class="report-actions">
              <button
                type="button"
                class="icon-button"
                title="Скачать ZIP"
                @click.stop="handleDownloadReport(report.id)"
              >
                ⬇
              </button>
              <button
                type="button"
                class="icon-button icon-button--danger"
                title="Удалить"
                @click.stop="handleDeleteReport(report.id)"
              >
                ✕
              </button>
            </div>
          </li>
        </ul>

        <div class="history-card">
          <div class="history-header">
            <span>History</span>
            <span v-if="historyInfo" class="history-meta">
              {{ historyInfo.records }} записей ·
              {{
                historyInfo.updated_at
                  ? formatDate(historyInfo.updated_at)
                  : 'нет данных'
              }}
            </span>
          </div>
          <div class="history-actions">
            <button
              type="button"
              class="text-button"
              @click="downloadHistory"
            >
              Скачать history.jsonl
            </button>
            <label class="text-button">
              Загрузить history.jsonl
              <input
                type="file"
                accept=".json,.jsonl"
                @change="handleHistoryUpload"
              />
            </label>
          </div>
        </div>
      </section>

      <section class="viewer">
        <button
          v-if="!sidebarVisible"
          type="button"
          class="viewer-toggle"
          @click="sidebarVisible = true"
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
    </main>
  </div>
</template>

<style scoped>
@import './App.css';
</style>
