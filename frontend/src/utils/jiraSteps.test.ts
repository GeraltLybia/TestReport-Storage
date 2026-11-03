import { describe, expect, it } from 'vitest'

import {
  allStepIds,
  buildRows,
  chosenCalls,
  chosenSteps,
  failureCall,
  foldedRepeats,
  groupState,
  initialExpanded,
  toggleGroup,
} from './jiraSteps'
import type { BugSection, BugStep, BugStepGroup } from '../types/jira'

function step(id: string, title: string, extra: Partial<BugStep> = {}): BugStep {
  return {
    id,
    kind: 'step',
    title,
    status: 'passed',
    duration: 10,
    onFailurePath: false,
    failureOrigin: false,
    message: null,
    call: null,
    children: [],
    ...extra,
  }
}

const poll: BugStepGroup = {
  id: 't.1.0~',
  kind: 'group',
  title: 'Получаем статус',
  status: 'passed',
  duration: 30,
  onFailurePath: false,
  failureOrigin: false,
  attempts: [step('t.1.0', 'Получаем статус'), step('t.1.1', 'Получаем статус'), step('t.1.2', 'Получаем статус')],
}

const sections: BugSection[] = [
  { id: 'setup', title: 'Подготовка', steps: [step('s.0', 'api_client')] },
  {
    id: 'test',
    title: 'Тест',
    steps: [
      step('t.0', 'Создать заказ', {
        call: { method: 'POST', url: 'http://h:1/orders', path: '/orders', status: '201' },
      }),
      step('t.1', 'Ждём статус', { children: [poll] }),
      step('t.2', 'Отменить заказ', {
        status: 'failed',
        onFailurePath: true,
        call: { method: 'PATCH', url: 'http://h:1/orders/1', path: '/orders/1', status: '409' },
        children: [
          step('t.2.0', 'Сверяем статус', {
            status: 'failed',
            onFailurePath: true,
            failureOrigin: true,
            message: 'AssertionError: 409\nassert',
          }),
        ],
      }),
    ],
  },
]

describe('jira steps', () => {
  it('collects every step id including attempts and sub-steps', () => {
    expect(allStepIds(sections)).toEqual(['s.0', 't.0', 't.1', 't.1.0', 't.1.1', 't.1.2', 't.2', 't.2.0'])
  })

  it('opens the way down to the failure and nothing else', () => {
    expect([...initialExpanded(sections)]).toEqual(['t.2'])
  })

  it('builds rows with sections, folded groups and expanded attempts', () => {
    const selected = new Set(['t.0', 't.1.2'])
    const collapsed = buildRows(sections, selected, new Set(['t.1']))
    const group = collapsed.find((row) => row.type === 'group')
    expect(group).toMatchObject({ depth: 1, state: 'mixed', selected: 1, expanded: false })
    expect(collapsed.filter((row) => row.type === 'section').map((row) => row.key)).toEqual([
      'section-setup',
      'section-test',
    ])

    const open = buildRows(sections, selected, new Set(['t.1', 't.1.0~']))
    const attempts = open.filter((row) => row.type === 'step' && row.attempt)
    expect(attempts.map((row) => (row.type === 'step' ? row.attempt : ''))).toEqual([
      'Попытка 1 из 3',
      'Попытка 2 из 3',
      'Попытка 3 из 3',
    ])
  })

  it('toggles a group: last attempt in, then everything out', () => {
    const on = toggleGroup(poll, new Set())
    expect([...on]).toEqual(['t.1.2'])
    expect(groupState(poll, new Set(['t.1.0', 't.1.1', 't.1.2']))).toBe('on')
    expect([...toggleGroup(poll, new Set(['t.1.0', 'x']))]).toEqual(['x'])
  })

  it('lists chosen steps the way the description renders them', () => {
    const chosen = chosenSteps(sections, new Set(['t.0', 't.1.2', 't.2.0']))
    expect(chosen).toHaveLength(1)
    expect(chosen[0]?.steps).toEqual([
      { id: 't.0', label: 'Создать заказ', depth: 0, sub: 'POST /orders → 201', failure: false, skipped: false },
      { id: 't.1.2', label: 'Получаем статус — попытка 3 из 3', depth: 0, sub: '', failure: false, skipped: false },
      { id: 't.2.0', label: 'Сверяем статус', depth: 0, sub: 'AssertionError: 409', failure: true, skipped: false },
    ])
  })

  it('finds calls, the failing request and folded repeats', () => {
    expect(chosenCalls(sections, new Set(['t.0', 't.2']))).toEqual([
      'POST http://h:1/orders → 201',
      'PATCH http://h:1/orders/1 → 409',
    ])
    expect(failureCall(sections)?.path).toBe('/orders/1')
    expect(foldedRepeats(sections)).toBe(2)
  })
})
