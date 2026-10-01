import type { CoverageMeasurement, CoverageMeasurementMeta, NewCoverageMeasurement } from '../types/coverage'

const API_BASE = (import.meta.env.VITE_API_BASE ?? '') as string

async function errorMessage(response: Response, fallback: string) {
  const payload = (await response.json().catch(() => null)) as { detail?: unknown } | null
  return typeof payload?.detail === 'string' && payload.detail.trim() ? payload.detail : fallback
}

export async function fetchCoverageMeasurements() {
  const response = await fetch(`${API_BASE}/api/coverage`)
  if (!response.ok) throw new Error(await errorMessage(response, 'Не удалось загрузить измерения'))
  return (await response.json()) as CoverageMeasurementMeta[]
}

export async function fetchCoverageMeasurement(id: string, signal?: AbortSignal) {
  const response = await fetch(`${API_BASE}/api/coverage/${encodeURIComponent(id)}`, { signal })
  if (!response.ok) throw new Error(await errorMessage(response, 'Не удалось загрузить измерение'))
  return (await response.json()) as CoverageMeasurement
}

export async function createCoverageMeasurement(input: NewCoverageMeasurement) {
  const form = new FormData()
  form.append('kind', input.kind)
  form.append('name', input.name)
  form.append('report_ids', input.reportIds.join(','))
  form.append('spec', input.spec)
  if (input.basePath?.trim()) form.append('base_path', input.basePath.trim())
  if (input.host?.trim()) form.append('host', input.host.trim())
  if (input.endpoint?.trim()) form.append('endpoint', input.endpoint.trim())
  const response = await fetch(`${API_BASE}/api/coverage`, { method: 'POST', body: form })
  if (!response.ok) throw new Error(await errorMessage(response, 'Не удалось рассчитать покрытие'))
  return (await response.json()) as CoverageMeasurement
}

export async function deleteCoverageMeasurement(id: string) {
  const response = await fetch(`${API_BASE}/api/coverage/${encodeURIComponent(id)}`, { method: 'DELETE' })
  if (!response.ok) throw new Error(await errorMessage(response, 'Не удалось удалить измерение'))
}
