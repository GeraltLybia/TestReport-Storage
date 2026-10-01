<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'

import type { GraphqlCoverageResult, GraphqlField, GraphqlTypeCoverage } from '../../../types/coverage'

const props = defineProps<{ result: GraphqlCoverageResult }>()

const NODE_WIDTH = 240
const HEAD = 32
const ROW = 24
const COLUMN_GAP = 110
const NODE_GAP = 28
const MAX_FIELDS_FULL = 30

const showAll = ref(false)
const query = ref('')
const selectedTypeName = ref<string | null>(null)
const selectedFieldName = ref<string | null>(null)

const typesByName = computed(() => new Map(props.result.types.map((type) => [type.name, type])))
const isCovered = (type: GraphqlTypeCoverage) => type.fields.some((field) => field.calls > 0)

/** Breadth-first depth from the root types, used as the graph column. */
const depth = computed(() => {
  const result = new Map<string, number>()
  const queue: string[] = []
  for (const type of props.result.types) {
    if (type.root) {
      result.set(type.name, 0)
      queue.push(type.name)
    }
  }
  while (queue.length) {
    const name = queue.shift() as string
    const type = typesByName.value.get(name)
    if (!type) continue
    const next = [...type.fields.map((field) => field.target), ...type.possibleTypes].filter(Boolean) as string[]
    for (const target of next) {
      if (!result.has(target)) {
        result.set(target, (result.get(name) ?? 0) + 1)
        queue.push(target)
      }
    }
  }
  return result
})

const visibleTypes = computed(() => {
  if (showAll.value) return props.result.types
  return props.result.types.filter(
    (type) =>
      type.root !== null ||
      isCovered(type) ||
      (type.kind === 'union' && type.possibleTypes.some((member) => {
        const memberType = typesByName.value.get(member)
        return memberType ? isCovered(memberType) : false
      })),
  )
})

type LaidOutNode = {
  type: GraphqlTypeCoverage
  x: number
  y: number
  height: number
  fields: GraphqlField[]
  hiddenFields: number
  covered: number
  total: number
}

const layout = computed(() => {
  const maxDepth = Math.max(0, ...depth.value.values())
  const columns = new Map<number, GraphqlTypeCoverage[]>()
  for (const type of visibleTypes.value) {
    const column = depth.value.get(type.name) ?? maxDepth + 1
    columns.set(column, [...(columns.get(column) ?? []), type])
  }
  const nodes = new Map<string, LaidOutNode>()
  let width = 0
  let height = 0
  ;[...columns.keys()]
    .sort((a, b) => a - b)
    .forEach((column, columnIndex) => {
      let y = 0
      const sorted = (columns.get(column) ?? []).sort(
        (a, b) => Number(isCovered(b)) - Number(isCovered(a)) || a.name.localeCompare(b.name),
      )
      for (const type of sorted) {
        const coveredFields = type.fields.filter((field) => field.calls > 0)
        const fields = showAll.value ? type.fields.slice(0, MAX_FIELDS_FULL) : coveredFields
        const hiddenFields = type.fields.length - fields.length
        const rows = fields.length + (hiddenFields ? 1 : 0) + (type.kind === 'union' ? type.possibleTypes.length : 0)
        const nodeHeight = HEAD + rows * ROW + 6
        const x = columnIndex * (NODE_WIDTH + COLUMN_GAP)
        nodes.set(type.name, {
          type,
          x,
          y,
          height: nodeHeight,
          fields,
          hiddenFields,
          covered: coveredFields.length,
          total: type.fields.length,
        })
        y += nodeHeight + NODE_GAP
        width = Math.max(width, x + NODE_WIDTH)
        height = Math.max(height, y)
      }
    })

  const edges: { key: string; d: string; covered: boolean }[] = []
  const curve = (x1: number, y1: number, x2: number, y2: number) => {
    const bend = Math.max(40, Math.abs(x2 - x1) / 2)
    return `M${x1} ${y1} C${x1 + bend} ${y1} ${x2 - bend} ${y2} ${x2} ${y2}`
  }
  for (const node of nodes.values()) {
    node.fields.forEach((field, index) => {
      const target = field.target ? nodes.get(field.target) : undefined
      if (!target || target === node) return
      const y1 = node.y + HEAD + index * ROW + ROW / 2
      edges.push({
        key: `${node.type.name}.${field.name}`,
        d: curve(node.x + NODE_WIDTH, y1, target.x, target.y + HEAD / 2),
        covered: field.calls > 0,
      })
    })
    if (node.type.kind === 'union') {
      node.type.possibleTypes.forEach((member, index) => {
        const target = nodes.get(member)
        if (!target) return
        const y1 = node.y + HEAD + index * ROW + ROW / 2
        edges.push({
          key: `${node.type.name}|${member}`,
          d: curve(node.x + NODE_WIDTH, y1, target.x, target.y + HEAD / 2),
          covered: isCovered(target.type),
        })
      })
    }
  }
  return { nodes: [...nodes.values()], edges, width: width + 40, height: height + 40 }
})

// ─── pan & zoom ───
const viewport = ref<HTMLElement | null>(null)
const scale = ref(1)
const offset = ref({ x: 20, y: 20 })
let drag: { x: number; y: number; ox: number; oy: number } | null = null

function startDrag(event: PointerEvent) {
  if ((event.target as HTMLElement).closest('button')) return
  drag = { x: event.clientX, y: event.clientY, ox: offset.value.x, oy: offset.value.y }
  ;(event.currentTarget as HTMLElement).setPointerCapture(event.pointerId)
}
function moveDrag(event: PointerEvent) {
  if (!drag) return
  offset.value = { x: drag.ox + event.clientX - drag.x, y: drag.oy + event.clientY - drag.y }
}
function endDrag() {
  drag = null
}
function zoomBy(factor: number, originX?: number, originY?: number) {
  const next = Math.min(2, Math.max(0.25, scale.value * factor))
  const rect = viewport.value?.getBoundingClientRect()
  const ox = originX ?? (rect ? rect.width / 2 : 0)
  const oy = originY ?? (rect ? rect.height / 2 : 0)
  offset.value = {
    x: ox - ((ox - offset.value.x) * next) / scale.value,
    y: oy - ((oy - offset.value.y) * next) / scale.value,
  }
  scale.value = next
}
function onWheel(event: WheelEvent) {
  const rect = viewport.value?.getBoundingClientRect()
  zoomBy(event.deltaY < 0 ? 1.1 : 1 / 1.1, rect ? event.clientX - rect.left : undefined, rect ? event.clientY - rect.top : undefined)
}
function fit() {
  const el = viewport.value
  if (!el) return
  const factor = Math.min(1, (el.clientWidth - 40) / layout.value.width, (el.clientHeight - 40) / layout.value.height)
  scale.value = Math.max(0.25, factor)
  offset.value = { x: 20, y: 20 }
}

watch(showAll, () => void nextTick(fit))
onMounted(() => void nextTick(fit))

// ─── side lists & details ───
const typeList = computed(() => {
  const needle = query.value.trim().toLowerCase()
  return props.result.types
    .filter((type) => type.kind !== 'union')
    .filter(
      (type) =>
        !needle ||
        type.name.toLowerCase().includes(needle) ||
        type.fields.some((field) => field.name.toLowerCase().includes(needle)),
    )
    .map((type) => {
      const covered = type.fields.filter((field) => field.calls > 0).length
      return { name: type.name, root: type.root, covered, total: type.fields.length, pct: type.fields.length ? Math.round((covered / type.fields.length) * 100) : 0 }
    })
    .sort((a, b) => Number(Boolean(b.root)) - Number(Boolean(a.root)) || b.covered - a.covered || a.name.localeCompare(b.name))
})

const selectedType = computed(() => (selectedTypeName.value ? (typesByName.value.get(selectedTypeName.value) ?? null) : null))
const selectedField = computed(() => selectedType.value?.fields.find((field) => field.name === selectedFieldName.value) ?? null)

function selectType(name: string, focus = true) {
  selectedTypeName.value = name
  selectedFieldName.value = null
  if (!focus) return
  const node = layout.value.nodes.find((item) => item.type.name === name)
  const el = viewport.value
  if (node && el) {
    offset.value = { x: el.clientWidth / 2 - (node.x + NODE_WIDTH / 2) * scale.value, y: 40 - node.y * scale.value }
  } else if (!node && !showAll.value) {
    showAll.value = true
  }
}

const s = computed(() => props.result.summary)
</script>

<template>
  <section class="cov-kpis" aria-label="Итоги">
    <article class="cov-card cov-kpi">
      <span>Покрыто полей</span>
      <strong>{{ s.coverage }}%</strong>
      <span class="cov-meter"><span :style="{ width: `${s.coverage}%` }"></span></span>
      <small>{{ s.coveredFields }} из {{ s.fields }} полей</small>
    </article>
    <article class="cov-card cov-kpi">
      <span>Корневые операции</span>
      <strong>{{ s.coveredRootFields }} / {{ s.rootFields }}</strong>
      <small>поля Query, Mutation и Subscription</small>
    </article>
    <article class="cov-card cov-kpi">
      <span>Типы с покрытием</span>
      <strong>{{ s.coveredTypes }} / {{ s.types }}</strong>
      <small>аргументов использовано: {{ s.usedArgs }} из {{ s.args }}</small>
    </article>
    <article class="cov-card cov-kpi">
      <span>Запросов в логах</span>
      <strong>{{ s.calls }}</strong>
      <small :class="{ 'tone-broken': s.invalidCalls }">
        {{ s.invalidCalls ? `${s.invalidCalls} не прошли валидацию по схеме` : 'все валидны по схеме' }}
      </small>
    </article>
  </section>

  <div class="cov-graph-layout">
    <aside class="cov-card cov-types" aria-label="Типы">
      <input v-model="query" type="search" class="cov-input" placeholder="Тип или поле" aria-label="Поиск по схеме" />
      <label class="cov-check"><input v-model="showAll" type="checkbox" />Показать всю схему</label>
      <ul class="cov-type-list">
        <li v-for="type in typeList" :key="type.name">
          <button
            type="button"
            :class="{ 'is-active': selectedTypeName === type.name, 'is-root': type.root }"
            @click="selectType(type.name)"
          >
            <span class="cov-mono">{{ type.name }}</span>
            <span class="cov-meter cov-meter--small"><span :style="{ width: `${type.pct}%` }"></span></span>
            <span class="cov-mono cov-ratio">{{ type.covered }}/{{ type.total }}</span>
          </button>
        </li>
      </ul>
      <div class="cov-legend">
        <span><i class="cov-legend-dot is-covered"></i>Поле запрашивалось в тестах</span>
        <span><i class="cov-legend-dot"></i>Поле не покрыто</span>
        <span><i class="cov-legend-line is-covered"></i>Связь использовалась</span>
      </div>
    </aside>

    <section
      ref="viewport"
      class="cov-graph"
      aria-label="Граф схемы"
      @pointerdown="startDrag"
      @pointermove="moveDrag"
      @pointerup="endDrag"
      @pointercancel="endDrag"
      @wheel.prevent="onWheel"
    >
      <div class="cov-graph-tools">
        <button type="button" aria-label="Приблизить" @click="zoomBy(1.2)">+</button>
        <button type="button" aria-label="Отдалить" @click="zoomBy(1 / 1.2)">−</button>
        <button type="button" @click="fit()">Вписать</button>
      </div>
      <p v-if="!layout.nodes.length" class="cov-empty">Нет типов для отображения.</p>
      <div
        class="cov-graph-stage"
        :style="{
          width: `${layout.width}px`,
          height: `${layout.height}px`,
          transform: `translate(${offset.x}px, ${offset.y}px) scale(${scale})`,
        }"
      >
        <svg :width="layout.width" :height="layout.height" aria-hidden="true">
          <path v-for="edge in layout.edges" :key="edge.key" :d="edge.d" :class="{ 'is-covered': edge.covered }" />
        </svg>
        <div
          v-for="node in layout.nodes"
          :key="node.type.name"
          class="cov-node"
          :class="{
            'is-root': node.type.root,
            'is-covered': node.covered > 0,
            'is-active': selectedTypeName === node.type.name,
          }"
          :style="{ left: `${node.x}px`, top: `${node.y}px`, width: '240px' }"
        >
          <button type="button" class="cov-node-head" @click="selectType(node.type.name, false)">
            <span class="cov-mono">{{ node.type.kind === 'union' ? `union ${node.type.name}` : node.type.name }}</span>
            <span v-if="node.type.kind !== 'union'" class="cov-mono">{{ node.covered }}/{{ node.total }}</span>
          </button>
          <div v-for="field in node.fields" :key="field.name" class="cov-node-row" :class="{ 'is-covered': field.calls > 0 }">
            <i></i>
            <span class="cov-mono">{{ field.name }}</span>
            <span class="cov-mono cov-node-type">{{ field.type }}</span>
          </div>
          <div v-for="member in node.type.possibleTypes" :key="member" class="cov-node-row cov-node-member">
            <span class="cov-mono">{{ member }}</span>
          </div>
          <div v-if="node.hiddenFields" class="cov-node-row cov-node-more">
            + {{ node.hiddenFields }} {{ showAll ? 'полей' : 'непокрытых полей' }}
          </div>
        </div>
      </div>
    </section>
  </div>

  <section v-if="selectedType" class="cov-card cov-type-detail" :aria-label="`Тип ${selectedType.name}`">
    <h2 class="cov-mono">{{ selectedType.name }}</h2>
    <div class="cov-type-detail-grid">
      <div class="cov-field-table">
        <button
          v-for="field in selectedType.fields"
          :key="field.name"
          type="button"
          class="cov-field-row"
          :class="{ 'is-covered': field.calls > 0, 'is-active': selectedFieldName === field.name }"
          @click="selectedFieldName = field.name"
        >
          <i></i>
          <span class="cov-mono">{{ field.name }}</span>
          <span class="cov-mono cov-node-type">{{ field.type }}</span>
          <span class="cov-mono">{{ field.calls || '—' }}</span>
        </button>
        <p v-if="!selectedType.fields.length" class="cov-hint">У union-типа нет собственных полей.</p>
      </div>
      <div class="cov-field-detail">
        <template v-if="selectedField">
          <h3 class="cov-mono">{{ selectedType.name }}.{{ selectedField.name }}</h3>
          <p class="cov-hint">{{ selectedField.calls }} запросов · {{ selectedField.tests.length }} тестов</p>
          <template v-if="selectedField.args.length">
            <h4>Аргументы</h4>
            <ul class="cov-plain">
              <li v-for="arg in selectedField.args" :key="arg.name">
                <span class="cov-code" :class="arg.calls ? 'cov-code--ok' : 'cov-code--missing'">{{ arg.name }}</span>
                {{ arg.calls ? `передавался ${arg.calls} раз` : 'не передавался' }}
              </li>
            </ul>
          </template>
          <h4>Тесты</h4>
          <p v-if="!selectedField.tests.length" class="cov-hint">Поле не запрашивалось.</p>
          <ul v-else class="cov-tests">
            <li v-for="test in selectedField.tests" :key="`${test.reportId}:${test.testId}`">
              <RouterLink :to="{ name: 'report-by-id', params: { reportId: test.reportId } }">
                <span>{{ test.name }}</span>
                <span v-if="test.fullName" class="cov-mono">{{ test.fullName }}</span>
              </RouterLink>
            </li>
          </ul>
        </template>
        <p v-else class="cov-hint">Выберите поле, чтобы увидеть аргументы и тесты.</p>
      </div>
    </div>
  </section>

  <section v-if="result.invalid.length" class="cov-card cov-unknown" aria-label="Невалидные запросы">
    <h2>Запросы, не прошедшие валидацию по схеме</h2>
    <p class="cov-hint">Схема устарела или запрос обращается к полям, которых в ней нет. Известные поля из таких запросов всё равно учтены.</p>
    <details v-for="(item, index) in result.invalid" :key="index" class="cov-invalid">
      <summary>{{ item.error }}</summary>
      <pre class="cov-mono">{{ item.query }}</pre>
    </details>
  </section>
</template>
