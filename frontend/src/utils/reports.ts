import type { Report } from '../types/reports'

export function formatDate(value: string | null) {
  if (!value) return '-'
  const date = new Date(value)
  return date.toLocaleString()
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

  if (report.entry_path) {
    const parts = report.entry_path.split('/')
    if (parts.length >= 2) {
      return parts[1]
    }
  }
  return report.name
}
