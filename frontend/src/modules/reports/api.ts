import type { HistoryInfo, Report } from './types'

async function parseApiError(response: Response, fallback: string) {
  const payload = await response.json().catch(() => null)
  return payload?.detail ?? fallback
}

export async function fetchReports() {
  const response = await fetch('/api/reports')
  if (!response.ok) {
    throw new Error(await parseApiError(response, 'Ошибка загрузки списка отчетов'))
  }
  return (await response.json()) as Report[]
}

export async function fetchHistoryInfo() {
  const response = await fetch('/api/history/info')
  if (!response.ok) {
    throw new Error(await parseApiError(response, 'Ошибка загрузки history'))
  }
  return (await response.json()) as HistoryInfo
}

export async function uploadReport(file: File) {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch('/api/reports/upload', {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    throw new Error(await parseApiError(response, 'Ошибка загрузки отчета'))
  }
}

export async function deleteReport(reportId: string) {
  const response = await fetch(`/api/reports/${reportId}`, { method: 'DELETE' })
  if (!response.ok) {
    throw new Error(await parseApiError(response, 'Ошибка удаления отчета'))
  }
}

export async function uploadHistory(file: File) {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch('/api/history', {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    throw new Error(await parseApiError(response, 'Ошибка загрузки history'))
  }
}
