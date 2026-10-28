export type JiraConfig = {
  enabled: boolean
  baseUrl: string | null
  projectKey: string | null
  issueType: string
}

export type JiraOption = { id: string; name: string | null; iconUrl?: string | null }

export type JiraMeta = {
  projectKey: string
  issueType: { id: string; name: string | null }
  priorities: JiraOption[]
  defaultPriority: string | null
  components: JiraOption[]
  fields: string[]
  /** Required fields of the project the bug form does not fill. */
  unsupportedRequired: { id: string; name: string | null }[]
}

export type JiraIssueLink = {
  key: string
  url: string | null
  summary: string | null
  status: string | null
  statusCategory: string | null
  testKey: string | null
  createdAt: string | null
}

export type BugApiCall = { method: string; url: string; path: string; status: string | null }

export type BugStep = {
  id: string
  kind: 'step'
  title: string
  status: string
  duration: number | null
  onFailurePath: boolean
  failureOrigin: boolean
  message: string | null
  call: BugApiCall | null
  children: BugNode[]
}

/** Consecutive steps with the same name (polling, retries) folded together. */
export type BugStepGroup = {
  id: string
  kind: 'group'
  title: string
  status: string
  duration: number | null
  onFailurePath: boolean
  failureOrigin: boolean
  attempts: BugStep[]
}

export type BugNode = BugStep | BugStepGroup

export type BugSection = { id: 'setup' | 'test' | 'teardown'; title: string; steps: BugNode[] }

export type BugAttachment = {
  id: string
  name: string
  title: string
  kind: 'log' | 'json' | 'image' | 'other'
  size: number | null
  defaultSelected: boolean
}

export type BugAssignee = { name: string; displayName: string; found: boolean | null }

export type BugDraft = {
  report: { id: string; name: string; createdAt: string | null; author: string | null; launchSource: string | null }
  test: {
    id: string
    name: string | null
    fullName: string | null
    testKey: string
    status: string
    duration: number | null
    signature: string | null
    tags: string[]
    parameters: { name: string; value: string }[]
  }
  error: { message: string | null; trace: string | null }
  stand: { host: string; url: string; name: string | null; origins: { origin: string; count: number }[] } | null
  sections: BugSection[]
  defaultSteps: string[]
  attachments: BugAttachment[]
  suggested: { summary: string; labels: string[]; assignee: BugAssignee | null }
  duplicates: { exact: JiraIssueLink | null; similar: JiraIssueLink[] }
  links: { report?: string; allure?: string }
}

export type BugLogMode = 'calls' | 'full' | 'none'

export type BugContent = {
  reportId: string
  testId: string
  steps: string[]
  logMode: BugLogMode
  attachments: string[]
  expected: string
  includeTrace: boolean
}

export type BugIssueRequest = BugContent & {
  summary: string
  priority: string | null
  components: string[]
  labels: string[]
  assignee: string | null
}

export type BugIssueResult = {
  key: string
  url: string
  summary: string
  steps: number
  logLines: number
  attachments: string[]
  warnings: string[]
}

export type BugCommentResult = { key: string; url: string; attachments: string[]; warnings: string[] }

export type BugPreview = { description: string; steps: number; logLines: number }
