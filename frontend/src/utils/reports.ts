import type { Report } from '../types/reports'

const DATE_LOCALE = 'ru-RU'

export function formatDate(value: string | null) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleString(DATE_LOCALE, {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function formatSize(bytes: number) {
  if (!bytes) return '0 B'

  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let unit = 0

  while (size >= 1024 && unit < units.length - 1) {
    size /= 1024
    unit += 1
  }

  return `${size.toFixed(1)} ${units[unit]}`
}

export function formatDuration(milliseconds: number | null | undefined) {
  if (milliseconds === null || milliseconds === undefined || Number.isNaN(milliseconds)) {
    return '-'
  }

  const safeValue = Math.max(0, Math.floor(milliseconds / 1000))
  const hours = Math.floor(safeValue / 3600)
  const minutes = Math.floor((safeValue % 3600) / 60)
  const secs = safeValue % 60

  return `${String(hours).padStart(2, '0')}:${String(minutes).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
}

export function getReportTitle(report: Report) {
  if (report.name) {
    return report.name
  }

  const entryName = report.entry_path?.split('/').pop()
  if (entryName) {
    return entryName
  }

  return report.id
}

export function getPassRate(report: Report) {
  const s = report.stats
  return s && s.total ? Math.round((s.passed / s.total) * 100) : 0
}

export function getRingStyle(report: Report) {
  const s = report.stats
  const percent = (value: number) => (s && s.total ? (value / s.total) * 100 : 0)

  return {
    '--ring-passed': percent(s?.passed ?? 0),
    '--ring-flaky': percent(s?.flaky ?? 0),
    '--ring-broken': percent(s?.broken ?? 0),
    '--ring-failed': percent(s?.failed ?? 0),
  }
}

export function getRingTitle(report: Report) {
  const s = report.stats
  const base = getReportTitle(report)
  if (!s) return base
  return `${base} — пройдено: ${s.passed} · сбоя: ${s.failed} · нестабильно: ${s.flaky} · сломано: ${s.broken} · всего: ${s.total}`
}

const RUN_DATE_PATTERN = /(\d{4})-(\d{2})-(\d{2})[ _T](\d{2})[-:](\d{2})/

/**
 * Splits a run label like "Allure Report 2026-09-22_11-13 user" into short
 * day/time parts for compact chart axes. Falls back to the raw label.
 */
export function parseRunLabel(label: string) {
  const match = RUN_DATE_PATTERN.exec(label)
  if (!match) return { day: label, time: '' }
  const [, , month, day, hours, minutes] = match
  return { day: `${day}.${month}`, time: `${hours}:${minutes}` }
}

/**
 * Splits a full test name ("Module.path#test_method" or "module.path.test_method")
 * into the module path and the test method for two-line display.
 */
export function splitTestName(name: string) {
  const separatorIndex = name.includes('#') ? name.lastIndexOf('#') : name.lastIndexOf('.')
  if (separatorIndex <= 0 || separatorIndex === name.length - 1) return { module: '', method: name }
  return { module: name.slice(0, separatorIndex), method: name.slice(separatorIndex + 1) }
}

/** Maps any Allure status to one of the status keys used for colors. */
export function statusTone(status: string | null | undefined) {
  const value = status?.trim().toLowerCase()
  if (value === 'passed' || value === 'failed' || value === 'broken') return value
  return 'other'
}

/** Short human duration: "850 ms", "7.9 s", "2 m 05 s", "1 h 27 m". */
export function formatShortDuration(milliseconds: number | null | undefined) {
  if (milliseconds === null || milliseconds === undefined || Number.isNaN(milliseconds)) return '-'
  const safe = Math.max(0, milliseconds)
  if (safe < 1000) return `${Math.round(safe)} ms`
  if (safe < 60_000) return `${(safe / 1000).toFixed(1)} s`
  const totalSeconds = Math.round(safe / 1000)
  if (totalSeconds < 3600) return `${Math.floor(totalSeconds / 60)} m ${String(totalSeconds % 60).padStart(2, '0')} s`
  const totalMinutes = Math.round(totalSeconds / 60)
  return `${Math.floor(totalMinutes / 60)} h ${String(totalMinutes % 60).padStart(2, '0')} m`
}

const REPORT_NAME_PATTERN = /(\d{4})-(\d{2})-(\d{2})[ _T](\d{2})[-:](\d{2})(?:\s+(\S+))?\s*$/

/**
 * Pulls the run moment and author out of report names such as
 * "Allure Report 2026-09-22_11-13 zpirozhenko". Returns null for other names.
 */
export function parseReportName(name: string) {
  const match = REPORT_NAME_PATTERN.exec(name.trim())
  if (!match) return null
  const [, year, month, day, hours, minutes, user] = match
  return { date: `${day}.${month}.${year}`, time: `${hours}:${minutes}`, user: user ?? null }
}

export function getReportTone(report: Report) {
  const status = report.status?.trim().toLowerCase()
  if (status === 'passed' || status === 'failed' || status === 'broken') return status
  const s = report.stats
  if (!s) return 'other'
  if (s.failed) return 'failed'
  if (s.broken) return 'broken'
  return s.total ? 'passed' : 'other'
}
