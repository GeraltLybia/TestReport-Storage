<script setup lang="ts">
import { computed } from 'vue'
import type { JiraField } from '../../../types/jira'
import { isEmptyField, optionLabel, optionValue, sameOption } from '../../../utils/jiraFields'

const props = defineProps<{ field: JiraField; disabled?: boolean; invalid?: boolean }>()
const model = defineModel<unknown>()
const multiple = computed(() => props.field.control === 'multiselect')
const selectedIndices = computed(() => props.field.allowedValues.flatMap((option, index) => {
  const selected = multiple.value ? Array.isArray(model.value) && model.value.some(v => sameOption(v, option)) : sameOption(model.value, option)
  return selected ? [String(index)] : []
}))
const parent = computed(() => props.field.allowedValues.find(v => sameOption(v, model.value)) as Record<string, unknown> | undefined)
const children = computed(() => (Array.isArray(parent.value?.children) ? parent.value.children : []) as unknown[])
const childIndex = computed(() => {
  const child = (model.value as Record<string, unknown> | null)?.child
  return children.value.findIndex(v => sameOption(child, v))
})
function select(event: Event) {
  const el = event.target as HTMLSelectElement
  const values = [...el.selectedOptions].filter(o => o.value !== '').map(o => optionValue(props.field.allowedValues[Number(o.value)]))
  model.value = multiple.value ? values : values[0] ?? null
}
function selectChild(event: Event) {
  const index = (event.target as HTMLSelectElement).value
  model.value = { ...(optionValue(model.value) as object), ...(index !== '' ? { child: optionValue(children.value[Number(index)]) } : {}) }
}
const text = computed(() => {
  const value = model.value
  if (props.field.control === 'user') return String((value as Record<string, unknown> | null)?.name ?? '')
  if (props.field.control === 'users') return Array.isArray(value) ? value.map(v => v.name).join(', ') : ''
  if (props.field.control === 'strings') return Array.isArray(value) ? value.join(', ') : ''
  if (props.field.control === 'datetime-local' && value) {
    const date = new Date(String(value))
    if (!Number.isNaN(date.getTime())) return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16)
  }
  return value == null ? '' : String(value)
})
function input(event: Event) {
  // Keep commas while typing a list; convert the completed text on blur/change.
  if (event.type === 'input' && ['users', 'strings'].includes(props.field.control)) return
  const value = (event.target as HTMLInputElement).value
  if (!value) { model.value = null; return }
  switch (props.field.control) {
    case 'number': model.value = Number(value); break
    case 'user': model.value = { name: value }; break
    case 'users': model.value = value.split(',').map(v => v.trim()).filter(Boolean).map(name => ({ name })); break
    case 'strings': model.value = value.split(',').map(v => v.trim()).filter(Boolean); break
    case 'datetime-local': model.value = new Date(value).toISOString(); break
    default: model.value = value
  }
}
</script>

<template>
  <div class="bug-field" :class="{ 'bug-field--wide': field.control === 'textarea' }">
    <label :for="`jira-${field.id}`" class="bug-label">{{ field.name }}<span v-if="field.required" aria-hidden="true"> *</span></label>
    <select
      v-if="['select', 'multiselect', 'cascade'].includes(field.control)"
      :id="`jira-${field.id}`" class="bug-input" :multiple="multiple" :disabled="disabled"
      :value="multiple ? selectedIndices : selectedIndices[0] ?? ''" :aria-required="field.required" :aria-invalid="invalid || undefined" @change="select"
    >
      <option v-if="!multiple" value="">Выберите значение</option>
      <option v-for="(option, index) in field.allowedValues" :key="index" :value="String(index)">{{ optionLabel(option) }}</option>
    </select>
    <select v-else-if="field.control === 'boolean'" :id="`jira-${field.id}`" v-model="model" class="bug-input" :disabled="disabled" :aria-required="field.required" :aria-invalid="invalid || undefined">
      <option :value="null">Не задано</option><option :value="true">Да</option><option :value="false">Нет</option>
    </select>
    <textarea v-else-if="field.control === 'textarea'" :id="`jira-${field.id}`" class="bug-input" :value="text" :disabled="disabled" :aria-required="field.required" :aria-invalid="invalid || undefined" @input="input"></textarea>
    <input v-else :id="`jira-${field.id}`" class="bug-input" :type="['number', 'date', 'datetime-local'].includes(field.control) ? field.control : 'text'" :step="field.control === 'number' ? (field.schema.type === 'integer' ? '1' : 'any') : undefined" :value="text" :disabled="disabled" :aria-required="field.required" :aria-invalid="invalid || undefined" @input="input" @change="input" />
    <template v-if="field.control === 'cascade' && children.length">
      <label :for="`jira-${field.id}-child`" class="bug-label">{{ field.name }} — уточнение</label>
      <select :id="`jira-${field.id}-child`" class="bug-input" :value="childIndex < 0 ? '' : String(childIndex)" :disabled="disabled" @change="selectChild">
        <option value="">Без уточнения</option>
        <option v-for="(option, index) in children" :key="index" :value="String(index)">{{ optionLabel(option) }}</option>
      </select>
    </template>
    <span v-if="['strings', 'users'].includes(field.control)" class="bug-field-note">Несколько значений — через запятую</span>
    <span v-if="invalid && isEmptyField(model)" class="bug-field-note tone-failed">Заполните обязательное поле</span>
  </div>
</template>
