export type CoverageKind = 'rest' | 'graphql'

export type CoverageTestRef = {
  name: string
  fullName: string | null
  reportId: string
  testId: string
}

export type RestCoverageSummary = {
  operations: number
  coveredOperations: number
  codes: number
  coveredCodes: number
  calls: number
  matchedCalls: number
  unknownCalls: number
  testsWithCalls: number
  totalTests: number
  coverage: number
}

export type GraphqlCoverageSummary = {
  fields: number
  coveredFields: number
  types: number
  coveredTypes: number
  rootFields: number
  coveredRootFields: number
  args: number
  usedArgs: number
  calls: number
  invalidCalls: number
  testsWithCalls: number
  totalTests: number
  coverage: number
}

export type CoverageMeasurementMeta = {
  id: string
  name: string
  kind: CoverageKind
  createdAt: string
  spec: {
    filename: string
    size: number
    title?: string
    version?: string
    basePath?: string
    hosts?: string[]
    endpoint?: string | null
  }
  reports: { id: string; name: string }[]
  summary: RestCoverageSummary | GraphqlCoverageSummary
}

export type RestOperation = {
  id: string
  method: string
  path: string
  tag: string
  summary: string
  calls: number
  codes: { code: string; calls: number }[]
  undocumentedCodes: { code: string; calls: number }[]
  tests: CoverageTestRef[]
}

export type RestCoverageResult = {
  kind: 'rest'
  spec: { title: string; version: string; basePath: string; hosts: string[] }
  summary: RestCoverageSummary
  operations: RestOperation[]
  unknown: { method: string; path: string; calls: number; codes: string[] }[]
}

export type GraphqlField = {
  name: string
  type: string
  target: string | null
  calls: number
  args: { name: string; calls: number }[]
  tests: CoverageTestRef[]
}

export type GraphqlTypeCoverage = {
  name: string
  kind: 'object' | 'interface' | 'union'
  root: 'query' | 'mutation' | 'subscription' | null
  fields: GraphqlField[]
  possibleTypes: string[]
}

export type GraphqlCoverageResult = {
  kind: 'graphql'
  spec: { roots: Record<string, string> }
  summary: GraphqlCoverageSummary
  types: GraphqlTypeCoverage[]
  invalid: { query: string; error: string }[]
}

export type CoverageMeasurement = CoverageMeasurementMeta & {
  result: RestCoverageResult | GraphqlCoverageResult
}

export type NewCoverageMeasurement = {
  kind: CoverageKind
  name: string
  spec: File
  reportIds: string[]
  basePath?: string
  host?: string
  endpoint?: string
}
