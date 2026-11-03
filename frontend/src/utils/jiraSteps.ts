import type { BugApiCall, BugNode, BugSection, BugStep, BugStepGroup } from '../types/jira'

export type CheckState = 'on' | 'off' | 'mixed'

export type StepRow =
  | { type: 'section'; key: string; title: string }
  | {
      type: 'step'
      key: string
      node: BugStep
      depth: number
      state: CheckState
      /** "Попытка 2 из 3" for an attempt of a folded group. */
      attempt: string | null
      expandable: boolean
      expanded: boolean
    }
  | { type: 'group'; key: string; node: BugStepGroup; depth: number; state: CheckState; selected: number; expanded: boolean }

function members(node: BugNode): BugNode[] {
  return node.kind === 'group' ? node.attempts : node.children
}

/** Every step id, attempts and sub-steps included (the «Все» preset). */
export function allStepIds(sections: BugSection[]): string[] {
  const ids: string[] = []
  const visit = (nodes: BugNode[]) => {
    for (const node of nodes) {
      if (node.kind === 'step') ids.push(node.id)
      visit(members(node))
    }
  }
  sections.forEach((section) => visit(section.steps))
  return ids
}

/** Rows opened at first: the way down to the failed step. */
export function initialExpanded(sections: BugSection[]): Set<string> {
  const ids = new Set<string>()
  const visit = (nodes: BugNode[]) => {
    for (const node of nodes) {
      if (node.onFailurePath && members(node).length) ids.add(node.id)
      visit(members(node))
    }
  }
  sections.forEach((section) => visit(section.steps))
  return ids
}

export function groupState(group: BugStepGroup, selected: Set<string>): CheckState {
  const count = group.attempts.filter((attempt) => selected.has(attempt.id)).length
  return count === 0 ? 'off' : count === group.attempts.length ? 'on' : 'mixed'
}

/** A group checkbox takes the last attempt in, or takes every attempt out. */
export function toggleGroup(group: BugStepGroup, selected: Set<string>): Set<string> {
  const next = new Set(selected)
  const last = group.attempts[group.attempts.length - 1]
  if (groupState(group, selected) === 'off') {
    if (last) next.add(last.id)
  } else {
    group.attempts.forEach((attempt) => next.delete(attempt.id))
  }
  return next
}

export function buildRows(sections: BugSection[], selected: Set<string>, expanded: Set<string>): StepRow[] {
  const rows: StepRow[] = []
  const pushStep = (node: BugStep, depth: number, attempt: string | null) => {
    const isOpen = expanded.has(node.id)
    rows.push({
      type: 'step',
      key: node.id,
      node,
      depth,
      state: selected.has(node.id) ? 'on' : 'off',
      attempt,
      expandable: node.children.length > 0,
      expanded: isOpen,
    })
    if (isOpen) visit(node.children, depth + 1)
  }
  const visit = (nodes: BugNode[], depth: number) => {
    for (const node of nodes) {
      if (node.kind === 'step') {
        pushStep(node, depth, null)
        continue
      }
      const isOpen = expanded.has(node.id)
      rows.push({
        type: 'group',
        key: node.id,
        node,
        depth,
        state: groupState(node, selected),
        selected: node.attempts.filter((attempt) => selected.has(attempt.id)).length,
        expanded: isOpen,
      })
      if (isOpen) {
        node.attempts.forEach((attempt, index) =>
          pushStep(attempt, depth + 1, `Попытка ${index + 1} из ${node.attempts.length}`),
        )
      }
    }
  }
  for (const section of sections) {
    rows.push({ type: 'section', key: `section-${section.id}`, title: section.title })
    visit(section.steps, 0)
  }
  return rows
}

export type ChosenStep = { id: string; label: string; depth: number; sub: string; failure: boolean; skipped: boolean }

export function callLabel(call: BugApiCall) {
  return `${call.method} ${call.path}${call.status ? ` → ${call.status}` : ''}`
}

/**
 * Chosen steps in execution order, as they go into the description: a sub-step
 * whose parent is unticked moves up a level (same rule as the backend).
 */
export function chosenSteps(sections: BugSection[], selected: Set<string>): { section: BugSection; steps: ChosenStep[] }[] {
  const out: { section: BugSection; steps: ChosenStep[] }[] = []
  for (const section of sections) {
    const steps: ChosenStep[] = []
    const take = (node: BugStep, depth: number, label: string) => {
      if (selected.has(node.id)) {
        const sub = node.call
          ? callLabel(node.call)
          : node.failureOrigin && node.message
            ? (node.message.split('\n')[0] ?? '')
            : ''
        steps.push({ id: node.id, label, depth, sub, failure: node.failureOrigin, skipped: node.status === 'skipped' })
        visit(node.children, depth + 1)
      } else {
        visit(node.children, depth)
      }
    }
    const visit = (nodes: BugNode[], depth: number) => {
      for (const node of nodes) {
        if (node.kind === 'group') {
          node.attempts.forEach((attempt, index) =>
            take(attempt, depth, `${attempt.title} — попытка ${index + 1} из ${node.attempts.length}`),
          )
        } else {
          take(node, depth, node.title)
        }
      }
    }
    visit(section.steps, 0)
    if (steps.length) out.push({ section, steps })
  }
  return out
}

/** Requests of the chosen steps, in order. */
export function chosenCalls(sections: BugSection[], selected: Set<string>): string[] {
  const lines: string[] = []
  const visit = (nodes: BugNode[]) => {
    for (const node of nodes) {
      if (node.kind === 'step' && node.call && selected.has(node.id)) {
        lines.push(`${node.call.method} ${node.call.url} → ${node.call.status ?? '—'}`)
      }
      visit(members(node))
    }
  }
  sections.forEach((section) => visit(section.steps))
  return lines
}

/** The request the test broke on: the deepest call on the failure path. */
export function failureCall(sections: BugSection[]): BugApiCall | null {
  let found: BugApiCall | null = null
  const visit = (nodes: BugNode[]) => {
    for (const node of nodes) {
      if (!node.onFailurePath) continue
      if (node.kind === 'step' && node.call) found = node.call
      visit(members(node))
    }
  }
  sections.forEach((section) => visit(section.steps))
  return found
}

/** Attempts hidden behind folded groups (all but one per group). */
export function foldedRepeats(sections: BugSection[]): number {
  let count = 0
  const visit = (nodes: BugNode[]) => {
    for (const node of nodes) {
      if (node.kind === 'group') count += node.attempts.length - 1
      visit(members(node))
    }
  }
  sections.forEach((section) => visit(section.steps))
  return count
}
