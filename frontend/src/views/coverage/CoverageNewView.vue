<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { createCoverageMeasurement } from '../../api/coverage'
import { useReports } from '../../composables/useReports'
import { formatDate, formatSize, getReportTitle } from '../../utils/reports'
import type { CoverageKind } from '../../types/coverage'

const router = useRouter()
const { reports } = useReports()

const kind = ref<CoverageKind>('rest')
const name = ref('')
const specFile = ref<File | null>(null)
const specSummary = ref<string | null>(null)
const specError = ref<string | null>(null)
const basePath = ref('')
const host = ref('')
const endpoint = ref('')
const selected = ref<Set<string>>(new Set())
const query = ref('')
const dragOver = ref(false)
const submitting = ref(false)
const submitError = ref<string | null>(null)

const HTTP_METHODS = ['get', 'put', 'post', 'delete', 'patch', 'head', 'options', 'trace']

async function inspectSpec(file: File) {
  specSummary.value = null
  specError.value = null
  const text = await file.text()
  if (kind.value === 'rest') {
    try {
      const document = JSON.parse(text) as {
        openapi?: string
        swagger?: string
        info?: { title?: string; version?: string }
        paths?: Record<string, Record<string, unknown>>
        servers?: { url?: string }[]
        basePath?: string
        host?: string
      }
      if (!document.paths) throw new Error('нет раздела paths')
      const operations = Object.values(document.paths).reduce(
        (sum, item) => sum + Object.keys(item ?? {}).filter((key) => HTTP_METHODS.includes(key)).length,
        0,
      )
      const version = document.openapi ? `OpenAPI ${document.openapi}` : `Swagger ${document.swagger ?? ''}`
      specSummary.value = `${version} · ${document.info?.title ?? 'API'} ${document.info?.version ?? ''} · ${operations} операций`
      const serverUrl = document.servers?.[0]?.url
      if (serverUrl) {
        try {
          const parsed = new URL(serverUrl, 'http://placeholder')
          basePath.value = parsed.pathname === '/' ? '' : parsed.pathname
          host.value = parsed.host === 'placeholder' ? '' : parsed.host
        } catch {
          /* keep manual values */
        }
      } else if (document.basePath) {
        basePath.value = document.basePath
        host.value = document.host ?? ''
      }
      if (!name.value) name.value = document.info?.title ?? ''
    } catch (exception) {
      specError.value = `Не похоже на openapi.json: ${exception instanceof Error ? exception.message : 'ошибка разбора'}`
    }
  } else {
    const types = (text.match(/^\s*(type|interface|union)\s+\w+/gm) ?? []).length
    specSummary.value = text.trim().startsWith('{')
      ? 'Результат интроспекции (JSON)'
      : `SDL · ${types} типов`
    if (!name.value) name.value = file.name.replace(/\.[^.]+$/, '')
  }
}

function setFile(file: File | null | undefined) {
  if (!file) return
  specFile.value = file
  void inspectSpec(file)
}

function onDrop(event: DragEvent) {
  dragOver.value = false
  setFile(event.dataTransfer?.files?.[0])
}

watch(kind, () => {
  specFile.value = null
  specSummary.value = null
  specError.value = null
})

const reportRows = computed(() => {
  const needle = query.value.trim().toLowerCase()
  return reports.value
    .filter((report) => !needle || getReportTitle(report).toLowerCase().includes(needle) || report.id.startsWith(needle))
    .map((report) => ({
      id: report.id,
      title: getReportTitle(report),
      meta: `${formatDate(report.created_at)} · ${report.stats?.total ?? 0} тестов · ${formatSize(report.size)}`,
      checked: selected.value.has(report.id),
    }))
})

function toggle(id: string) {
  const next = new Set(selected.value)
  if (next.has(id)) next.delete(id)
  else next.add(id)
  selected.value = next
}

function toggleAll() {
  const allSelected = reportRows.value.every((row) => row.checked)
  selected.value = allSelected ? new Set() : new Set(reportRows.value.map((row) => row.id))
}

const canSubmit = computed(() => Boolean(specFile.value) && !specError.value && selected.value.size > 0 && !submitting.value)

async function submit() {
  if (!specFile.value || !canSubmit.value) return
  submitting.value = true
  submitError.value = null
  try {
    const created = await createCoverageMeasurement({
      kind: kind.value,
      name: name.value,
      spec: specFile.value,
      reportIds: [...selected.value],
      basePath: kind.value === 'rest' ? basePath.value : undefined,
      host: kind.value === 'rest' ? host.value : undefined,
      endpoint: kind.value === 'graphql' ? endpoint.value : undefined,
    })
    await router.push({ name: 'coverage-by-id', params: { measurementId: created.id } })
  } catch (exception) {
    submitError.value = exception instanceof Error ? exception.message : 'Не удалось рассчитать покрытие'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="cov-view">
    <header class="cov-head">
      <div>
        <span class="cov-eyebrow">Покрытие API</span>
        <h1>Новое измерение</h1>
        <p>
          Загрузите спецификацию или схему и выберите отчёты. Покрытие считается по log-вложению каждого теста — строкам
          «Запрос / Ответ» из api_controller.
        </p>
      </div>
    </header>

    <form class="cov-new" @submit.prevent="submit">
      <div class="cov-new-main">
        <section class="cov-card cov-step" aria-labelledby="step-spec">
          <h2 id="step-spec"><span class="cov-step-num">1</span>Что измеряем</h2>
          <div class="cov-kind-pick" role="radiogroup" aria-label="Тип API">
            <label :class="{ 'is-active': kind === 'rest' }">
              <input v-model="kind" type="radio" value="rest" />
              <strong>REST · OpenAPI</strong>
              <span>openapi.json / swagger.json</span>
            </label>
            <label :class="{ 'is-active': kind === 'graphql' }">
              <input v-model="kind" type="radio" value="graphql" />
              <strong>GraphQL · схема</strong>
              <span>schema.graphql (SDL) или интроспекция .json</span>
            </label>
          </div>

          <label
            class="cov-drop"
            :class="{ 'is-over': dragOver }"
            @dragover.prevent="dragOver = true"
            @dragleave="dragOver = false"
            @drop.prevent="onDrop"
          >
            <svg viewBox="0 0 24 24" aria-hidden="true">
              <path d="M12 16V4M7 9l5-5 5 5" />
              <path d="M4 16v3a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-3" />
            </svg>
            <strong>{{ specFile ? specFile.name : kind === 'rest' ? 'Загрузите openapi.json' : 'Загрузите схему GraphQL' }}</strong>
            <span v-if="specSummary">{{ specSummary }}</span>
            <span v-else>Перетащите файл сюда или нажмите, чтобы выбрать</span>
            <input
              type="file"
              :accept="kind === 'rest' ? '.json,application/json' : '.graphql,.gql,.graphqls,.json'"
              @change="setFile(($event.target as HTMLInputElement).files?.[0])"
            />
          </label>
          <p v-if="specError" class="cov-field-error" role="alert">{{ specError }}</p>

          <div v-if="kind === 'rest'" class="cov-fields">
            <label>
              Хост сервиса
              <input v-model="host" class="cov-input cov-mono" placeholder="host:4001 — пусто: любой хост" />
            </label>
            <label>
              Base path
              <input v-model="basePath" class="cov-input cov-mono" placeholder="/api/driver/v1" />
            </label>
            <p class="cov-hint">Запросы на другие хосты и пути вне base path в измерение не попадут.</p>
          </div>
          <div v-else class="cov-fields">
            <label class="cov-fields-wide">
              GraphQL endpoint из логов
              <input v-model="endpoint" class="cov-input cov-mono" placeholder="http://host:4001/graphql — пусто: все эндпоинты" />
            </label>
          </div>
        </section>

        <section class="cov-card cov-step" aria-labelledby="step-reports">
          <h2 id="step-reports">
            <span class="cov-step-num">2</span>Отчёты
            <span class="cov-step-aside">Выбрано {{ selected.size }} из {{ reports.length }}</span>
          </h2>
          <div class="cov-toolbar">
            <input v-model="query" type="search" class="cov-input" placeholder="Имя отчёта или ID" aria-label="Поиск отчётов" />
            <button type="button" class="cov-ghost" @click="toggleAll()">Выбрать все</button>
          </div>
          <p v-if="!reports.length" class="cov-empty">Нет загруженных отчётов.</p>
          <div v-else class="cov-report-list">
            <label v-for="row in reportRows" :key="row.id" class="cov-report" :class="{ 'is-active': row.checked }">
              <input type="checkbox" :checked="row.checked" @change="toggle(row.id)" />
              <span>
                <strong>{{ row.title }}</strong>
                <span>{{ row.meta }}</span>
              </span>
            </label>
          </div>
        </section>
      </div>

      <aside class="cov-card cov-summary" aria-label="Итог">
        <h2>Итог</h2>
        <label class="cov-label">
          Название
          <input v-model="name" class="cov-input" placeholder="Например, Регресс Claims · октябрь" />
        </label>
        <dl>
          <div><dt>Тип</dt><dd>{{ kind === 'rest' ? 'REST · OpenAPI' : 'GraphQL' }}</dd></div>
          <div><dt>Файл</dt><dd class="cov-mono">{{ specFile?.name ?? '—' }}</dd></div>
          <div><dt>Отчётов</dt><dd class="cov-mono">{{ selected.size }}</dd></div>
        </dl>
        <p class="cov-hint">Результат сохраняется снимком: новые отчёты и изменения спецификации его не меняют.</p>
        <p v-if="submitError" class="cov-field-error" role="alert">{{ submitError }}</p>
        <button type="submit" class="cov-primary" :disabled="!canSubmit">
          {{ submitting ? 'Считаем…' : 'Рассчитать покрытие' }}
        </button>
        <RouterLink class="cov-ghost" :to="{ name: 'coverage' }">Отмена</RouterLink>
      </aside>
    </form>
  </div>
</template>

<style src="../../assets/style/views/coverage/Coverage.css"></style>
