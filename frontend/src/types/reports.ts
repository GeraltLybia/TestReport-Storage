export type ReportStats = {
  total: number
  passed: number
  failed: number
  flaky: number
  broken: number
}

export type Report = {
  id: string
  name: string
  created_at: string
  size: number
  entry_path?: string | null
  stats?: ReportStats | null
  status?: string | null
  duration?: number | null
}

export type HistoryInfo = {
  records: number
  updated_at: string | null
  size: number
}
