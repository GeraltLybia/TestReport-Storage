<script setup lang="ts">
import { useReports } from '../../../composables/useReports'
import { useTheme } from '../../../composables/useTheme'

const { handleUploadReport, reports, uploading } = useReports()
const { theme } = useTheme()
</script>

<template>
  <aside class="app-sidebar">
    <RouterLink class="app-brand" :to="{ name: 'dashboard' }" aria-label="TestReport Storage — на дашборд">
      <svg class="app-brand-mark" viewBox="0 0 512 464" aria-hidden="true">
        <rect x="180" y="44" width="152" height="76" rx="22" fill="#22CCD2" />
        <rect x="88" y="144" width="336" height="76" rx="22" fill="#1AB4BC" />
        <rect x="40" y="244" width="172" height="76" rx="22" fill="#18A2AB" />
        <rect x="300" y="244" width="172" height="76" rx="22" fill="#18A2AB" />
        <rect x="16" y="344" width="172" height="76" rx="22" fill="#147E88" />
        <rect x="324" y="344" width="172" height="76" rx="22" fill="#147E88" />
      </svg>
      <span class="app-brand-name"><strong>TestReport</strong><span>Storage</span></span>
    </RouterLink>

    <nav class="app-nav" aria-label="Основная навигация">
      <RouterLink class="app-nav-link" :to="{ name: 'dashboard' }">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <rect x="3" y="3" width="7" height="9" rx="1.5" />
          <rect x="14" y="3" width="7" height="5" rx="1.5" />
          <rect x="14" y="12" width="7" height="9" rx="1.5" />
          <rect x="3" y="16" width="7" height="5" rx="1.5" />
        </svg>
        Дашборд
      </RouterLink>
      <RouterLink
        class="app-nav-link"
        :class="{ 'router-link-active': $route.name === 'report-by-id' }"
        :to="{ name: 'reports' }"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8z" />
          <path d="M14 3v5h5M9 13h6M9 17h4" />
        </svg>
        Отчёты
        <span v-if="reports.length" class="app-nav-count">{{ reports.length }}</span>
      </RouterLink>
      <RouterLink
        class="app-nav-link"
        :class="{ 'router-link-active': $route.name === 'run-by-id' }"
        :to="{ name: 'runs' }"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M3 12a9 9 0 1 0 3-6.7L3 8" />
          <path d="M3 3v5h5M12 7v5l3 2" />
        </svg>
        Прогоны
      </RouterLink>
      <RouterLink
        class="app-nav-link"
        :class="{ 'router-link-active': String($route.name ?? '').startsWith('coverage') }"
        :to="{ name: 'coverage' }"
      >
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 3a9 9 0 1 0 9 9h-9z" />
          <path d="M15 3.5A9 9 0 0 1 20.5 9H15z" />
        </svg>
        Покрытие API
      </RouterLink>
    </nav>

    <div class="app-sidebar-footer">
      <label class="app-upload" :class="{ 'app-upload--busy': uploading }" title="Allure-отчёт в ZIP-архиве">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <path d="M12 16V4M7 9l5-5 5 5" />
          <path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
        </svg>
        <span>{{ uploading ? 'Загрузка…' : 'Загрузить отчёт' }}</span>
        <input type="file" accept=".zip" :disabled="uploading" @change="handleUploadReport" />
      </label>

      <div class="app-theme" role="group" aria-label="Тема оформления">
        <button type="button" aria-label="Светлая тема" :aria-pressed="theme === 'light'" @click="theme = 'light'">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <circle cx="12" cy="12" r="4" />
            <path
              d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"
            />
          </svg>
          <span class="app-theme-text">Светлая</span>
        </button>
        <button type="button" aria-label="Тёмная тема" :aria-pressed="theme === 'dark'" @click="theme = 'dark'">
          <svg viewBox="0 0 24 24" aria-hidden="true">
            <path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z" />
          </svg>
          <span class="app-theme-text">Тёмная</span>
        </button>
      </div>
    </div>
  </aside>
</template>

<style scoped src="../../../assets/style/components/layout/AppSidebar.css"></style>
