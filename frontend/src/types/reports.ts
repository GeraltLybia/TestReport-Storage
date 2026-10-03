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

export type HistoryLabel = {
  name: string
  value: string
}

export type HistoryTestResult = {
  id?: string
  name?: string
  fullName?: string
  environment?: string
  status?: string
  start?: number
  stop?: number
  duration?: number
  message?: string
  trace?: string
  labels?: HistoryLabel[]
  url?: string
  historyId?: string
  reportLinks?: string[]
}

export type HistoryRun = {
  uuid: string
  name: string
  timestamp: number
  knownTestCaseIds?: string[]
  testResults?: Record<string, HistoryTestResult>
  metrics?: Record<string, unknown>
  url?: string
}

export type HistoryAggregateStats = {
  total: number
  passed: number
  failed: number
  broken: number
  flaky: number
  other: number
}

export type HistoryFilterOptions = {
  tags: string[]
  suites: string[]
  environments: string[]
}

export type HistoryPoint = {
  key: string
  label: string
  total: number
  passed: number
  failed: number
  broken: number
  passRate: number
  reportName: string | null
}

export type TrendPoint = HistoryPoint & {
  reportId: string | null
}

export type HistoryTagHealth = {
  tag: string
  total: number
  incidents: number
  healthyRate: number
  passedRuns: number
  failedRuns: number
  brokenRuns: number
}

export type HistoryFailureSignature = {
  signature: string
  count: number
}

export type HistoryUnstableTest = {
  key: string
  name: string
  totalRuns: number
  incidents: number
  stability: number
  passedRuns: number
  failedRuns: number
  brokenRuns: number
  lastStatus: string
  /** Latest statuses, oldest first (up to 10). */
  recentStatuses?: string[]
}

export type HistoryStabilityDetailItem = {
  key: string
  name: string
  lastStatus: string
  incidents: number
  totalRuns: number
}

export type HistoryStabilitySummary = {
  uniqueTests: number
  flaky: number
  alwaysFailed: number
  alwaysPassed: number
}

export type StabilityBucketKey = 'flaky' | 'alwaysFailed' | 'alwaysPassed' | 'incidents'

export type HistoryTestDetailsEntry = {
  status?: string
  duration?: number
  environment?: string
  message?: string
  start?: number
}

export type HistorySelectedTestDetails = {
  name: string
  lastStatus: string
  totalRuns: number
  incidents: number
  history: HistoryTestDetailsEntry[]
}

export type RecentReportItem = {
  id: string
  label: string
  healthy: number
  incidents: number
  total: number
  selected: boolean
}

export type ProblemRunItem = {
  report: Report
  incidents: number
}

export type HistoryDashboardSummary = {
  filterOptions: HistoryFilterOptions
  filteredRunCount: number
  aggregateStats: HistoryAggregateStats
  p95Duration: number | null
  passRate: number
  incidentRate: number
  stabilitySummary: HistoryStabilitySummary
  stabilityDetails: {
    flaky: HistoryStabilityDetailItem[]
    alwaysFailed: HistoryStabilityDetailItem[]
    alwaysPassed: HistoryStabilityDetailItem[]
    incidents: HistoryStabilityDetailItem[]
  }
  trendPoints: HistoryPoint[]
  topUnstableTests: HistoryUnstableTest[]
  failureSignatures: HistoryFailureSignature[]
  tagHealth: HistoryTagHealth[]
}

/** How a result differs from the previous result of the same test in history. */
export type ResultChange = 'new_failure' | 'still_failing' | 'fixed' | 'new_test'

export type PreviousResult = {
  status: string
  runName?: string | null
  runUuid?: string | null
  at?: number | null
}

export type ResultChanges = {
  newFailures: number
  stillFailing: number
  fixed: number
  newTests: number
}

export type TestResultItem = {
  id: string
  /** Key of the test in history (full name); opens the test details drawer. */
  testKey?: string | null
  name: string
  fullName?: string | null
  status: string
  duration?: number | null
  message?: string | null
  suite?: string | null
  tags?: string[]
  /** First line of the error, same as failure signatures on the dashboard. */
  signature?: string | null
  change?: ResultChange | null
  previous?: PreviousResult | null
}

/** `incidents` = failed + broken; `changes` = new failures, fixed tests and new failing tests. */
export type ResultStatusFilter = 'incidents' | 'changes' | 'all'

export type HistoryRunSummary = {
  uuid: string
  name: string
  timestamp: number
  total: number
  passed: number
  failed: number
  broken: number
  other: number
  duration: number | null
  passRate: number
  status: string
}

export type RunStatusFilter = 'all' | 'failed' | 'broken' | 'passed'

export type HistoryRunList = {
  total: number
  counts: Record<RunStatusFilter, number>
  items: HistoryRunSummary[]
}

export type HistoryRunResults = {
  run: HistoryRunSummary
  total: number
  items: TestResultItem[]
  changes: ResultChanges
}

export type ReportResults = {
  total: number
  items: TestResultItem[]
  /** Null when there is no history to compare with. */
  changes?: ResultChanges | null
}
