<script setup lang="ts">
import { computed, ref, watch } from 'vue'

import type { RestCoverageResult, RestOperation } from '../../../types/coverage'

const props = defineProps<{ result: RestCoverageResult }>()

type Filter = 'all' | 'covered' | 'partial' | 'missing'
const filter = ref<Filter>('all')
const query = ref('')
const selectedId = ref<string | null>(props.result.operations.find((op) => op.calls)?.id ?? props.result.operations[0]?.id ?? null)

const isPartial = (op: RestOperation) => op.calls > 0 && op.codes.some((code) => code.calls === 0)
const matches = (op: RestOperation, value: Filter) =>
  value === 'all' ||
  (value === 'covered' && op.calls > 0) ||
  (value === 'missing' && op.calls === 0) ||
  (value === 'partial' && isPartial(op))

const filters = computed(() =>
  (
    [
      ['all', 'Все'],
      ['covered', 'Покрыто'],
      ['partial', 'Частично'],
      ['missing', 'Не покрыто'],
    ] as [Filter, string][]
  ).map(([key, label]) => ({ key, label, count: props.result.operations.filter((op) => matches(op, key)).length })),
)

const groups = computed(() => {
  const needle = query.value.trim().toLowerCase()
  const byTag = new Map<string, RestOperation[]>()
  for (const op of props.result.operations) {
    const list = byTag.get(op.tag) ?? []
    list.push(op)
    byTag.set(op.tag, list)
  }
  return [...byTag.entries()]
    .map(([tag, ops]) => {
      const covered = ops.filter((op) => op.calls > 0).length
      const visible = ops.filter(
        (op) =>
          matches(op, filter.value) &&
          (!needle || op.path.toLowerCase().includes(needle) || op.summary.toLowerCase().includes(needle) || tag.toLowerCase().includes(needle)),
      )
      return { tag, covered, total: ops.length, pct: Math.round((covered / ops.length) * 100), ops: visible }
    })
    .filter((group) => group.ops.length)
})

const selected = computed(() => props.result.operations.find((op) => op.id === selectedId.value) ?? null)
const TESTS_PREVIEW = 8
const showAllTests = ref(false)
const visibleTests = computed(() =>
  showAllTests.value ? (selected.value?.tests ?? []) : (selected.value?.tests ?? []).slice(0, TESTS_PREVIEW),
)
watch(selectedId, () => (showAllTests.value = false))

const s = computed(() => props.result.summary)
const codesPct = computed(() => (s.value.codes ? Math.round((s.value.coveredCodes / s.value.codes) * 100) : 0))

function codeClass(code: string, calls: number) {
  if (!calls) return 'cov-code--missing'
  return code.startsWith('2') ? 'cov-code--ok' : 'cov-code--err'
}
</script>

<template>
  <section class="cov-kpis" aria-label="Итоги">
    <article class="cov-card cov-kpi">
      <span>Покрыто операций</span>
      <strong>{{ s.coverage }}%</strong>
      <span class="cov-meter"><span :style="{ width: `${s.coverage}%` }"></span></span>
      <small>{{ s.coveredOperations }} из {{ s.operations }} операций</small>
    </article>
    <article class="cov-card cov-kpi">
      <span>Коды ответов</span>
      <strong>{{ codesPct }}%</strong>
      <small>{{ s.coveredCodes }} из {{ s.codes }} описанных кодов</small>
    </article>
    <article class="cov-card cov-kpi">
      <span>Вне спецификации</span>
      <strong :class="{ 'tone-broken': s.unknownCalls }">{{ s.unknownCalls }}</strong>
      <small>эндпоинтов нет в openapi.json</small>
    </article>
    <article class="cov-card cov-kpi">
      <span>Тестов с вызовами</span>
      <strong>{{ s.testsWithCalls }}</strong>
      <small>из {{ s.totalTests }} тестов с log-вложением · {{ s.matchedCalls }} из {{ s.calls }} запросов сопоставлено</small>
    </article>
  </section>

  <p class="cov-hint cov-hosts">
    <template v-if="result.spec.hosts.length">
      Учтены запросы к {{ result.spec.hostFilter?.length ? 'указанным хостам' : 'хостам сервиса' }}:
      <span class="cov-mono">{{ result.spec.hosts.join(', ') }}</span>.
    </template>
    <template v-else>Ни один запрос из логов не совпал с операциями спецификации — проверьте base path и хост.</template>
    <template v-if="result.spec.otherHosts?.length">
      Не относятся к сервису:
      <span v-for="(item, index) in result.spec.otherHosts" :key="item.host">
        <span class="cov-mono">{{ item.host }}</span> ({{ item.calls }}){{ index < result.spec.otherHosts.length - 1 ? ', ' : '' }}
      </span>.
    </template>
  </p>

  <div class="cov-split">
    <section class="cov-card cov-ops" aria-label="Операции">
      <div class="cov-toolbar">
        <div class="cov-segmented" role="group" aria-label="Фильтр">
          <button v-for="item in filters" :key="item.key" type="button" :aria-pressed="filter === item.key" @click="filter = item.key">
            {{ item.label }} <span class="cov-count">{{ item.count }}</span>
          </button>
        </div>
        <input v-model="query" type="search" class="cov-input" placeholder="Путь, тег или описание" aria-label="Поиск операций" />
      </div>
      <p v-if="!groups.length" class="cov-empty">Ничего не найдено.</p>
      <div v-for="group in groups" :key="group.tag" class="cov-group">
        <div class="cov-group-head">
          <strong>{{ group.tag }}</strong>
          <span>{{ group.covered }} из {{ group.total }}</span>
          <span class="cov-meter cov-meter--small"><span :style="{ width: `${group.pct}%` }"></span></span>
          <span class="cov-mono">{{ group.pct }}%</span>
        </div>
        <button
          v-for="op in group.ops"
          :key="op.id"
          type="button"
          class="cov-op"
          :class="{ 'is-active': op.id === selectedId, 'is-missing': !op.calls }"
          :aria-pressed="op.id === selectedId"
          @click="selectedId = op.id"
        >
          <span class="cov-method" :class="`cov-method--${op.method.toLowerCase()}`">{{ op.method }}</span>
          <span class="cov-op-main">
            <span class="cov-mono">{{ op.path }}</span>
            <span v-if="op.summary">{{ op.summary }}</span>
          </span>
          <span class="cov-codes">
            <span
              v-for="code in op.codes"
              :key="code.code"
              class="cov-code"
              :class="codeClass(code.code, code.calls)"
              :title="code.calls ? `${code.calls} ответов` : 'не встречался в логах'"
              >{{ code.code }}</span
            >
          </span>
          <span class="cov-mono cov-calls">{{ op.calls || '—' }}</span>
        </button>
      </div>
    </section>

    <aside v-if="selected" class="cov-card cov-detail" aria-label="Детали операции">
      <div class="cov-detail-top">
        <span class="cov-method" :class="`cov-method--${selected.method.toLowerCase()}`">{{ selected.method }}</span>
        <span>{{ selected.tag }}</span>
      </div>
      <h2 class="cov-mono">{{ result.spec.basePath }}{{ selected.path }}</h2>
      <p v-if="selected.summary">{{ selected.summary }}</p>
      <div class="cov-mini-grid">
        <div><span>Вызовов</span><strong>{{ selected.calls }}</strong></div>
        <div><span>Тестов</span><strong>{{ selected.tests.length }}</strong></div>
      </div>
      <h3>Коды ответов</h3>
      <ul class="cov-plain">
        <li v-for="code in selected.codes" :key="code.code">
          <span class="cov-code" :class="codeClass(code.code, code.calls)">{{ code.code }}</span>
          {{ code.calls ? `${code.calls} ответов` : 'не встречался в логах' }}
        </li>
        <li v-for="code in selected.undocumentedCodes" :key="`u-${code.code}`">
          <span class="cov-code cov-code--err">{{ code.code }}</span>
          {{ code.calls }} ответов · <em>не описан в спецификации</em>
        </li>
      </ul>
      <h3>Тесты, которые вызывают операцию</h3>
      <p v-if="!selected.tests.length" class="cov-hint">Ни один тест не вызывал эту операцию.</p>
      <ul v-else class="cov-tests">
        <li v-for="test in visibleTests" :key="`${test.reportId}:${test.testId}`">
          <RouterLink :to="{ name: 'report-by-id', params: { reportId: test.reportId } }">
            <span>{{ test.name }}</span>
            <span v-if="test.fullName" class="cov-mono">{{ test.fullName }}</span>
          </RouterLink>
        </li>
      </ul>
      <button
        v-if="selected.tests.length > TESTS_PREVIEW && !showAllTests"
        type="button"
        class="cov-link"
        @click="showAllTests = true"
      >
        Показать все {{ selected.tests.length }}
      </button>
    </aside>
  </div>

  <section v-if="result.unknown.length" class="cov-card cov-unknown" aria-label="Вне спецификации">
    <h2>Вызовы вне спецификации</h2>
    <p class="cov-hint">Запросы из логов, которым не нашлось операции в openapi.json — устаревшая документация или ошибка в пути.</p>
    <div v-for="item in result.unknown" :key="`${item.method} ${item.path}`" class="cov-unknown-row">
      <span class="cov-method" :class="`cov-method--${item.method.toLowerCase()}`">{{ item.method }}</span>
      <span class="cov-mono">{{ item.path }}</span>
      <span class="cov-mono">{{ item.codes.join(', ') }}</span>
      <span class="cov-mono">{{ item.calls }} выз.</span>
    </div>
  </section>
</template>
