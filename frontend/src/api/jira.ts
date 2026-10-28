import { apiUrl, parseApiError } from './reports'
import type {
  BugCommentResult,
  BugContent,
  BugDraft,
  BugIssueRequest,
  BugIssueResult,
  BugPreview,
  JiraConfig,
  JiraIssueLink,
  JiraMeta,
} from '../types/jira'

async function request<T>(path: string, fallback: string, init?: RequestInit): Promise<T> {
  const response = await fetch(apiUrl(path), init)
  if (!response.ok) throw new Error(await parseApiError(response, fallback))
  return (await response.json()) as T
}

function post(body: unknown, signal?: AbortSignal): RequestInit {
  return { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body), signal }
}

export function fetchJiraConfig() {
  return request<JiraConfig>('/api/jira/config', 'Не удалось получить настройки Jira')
}

export function fetchJiraMeta() {
  return request<JiraMeta>('/api/jira/meta', 'Не удалось получить поля задачи из Jira')
}

export function fetchBugDraft(reportId: string, testId: string, signal?: AbortSignal) {
  const query = new URLSearchParams({ report_id: reportId, test_id: testId })
  return request<BugDraft>(`/api/jira/draft?${query}`, 'Не удалось собрать черновик бага', { signal })
}

export function previewBug(content: BugContent, signal?: AbortSignal) {
  return request<BugPreview>('/api/jira/preview', 'Не удалось собрать описание', post(content, signal))
}

export function createBug(payload: BugIssueRequest) {
  return request<BugIssueResult>('/api/jira/issues', 'Не удалось создать задачу в Jira', post(payload))
}

export function commentBug(key: string, content: BugContent) {
  return request<BugCommentResult>(
    `/api/jira/issues/${encodeURIComponent(key)}/comments`,
    'Не удалось добавить комментарий в Jira',
    post(content),
  )
}

export function fetchJiraLinks(reportId: string, signal?: AbortSignal) {
  const query = new URLSearchParams({ report_id: reportId })
  return request<{ items: Record<string, JiraIssueLink> }>(`/api/jira/links?${query}`, 'Не удалось получить задачи Jira', {
    signal,
  })
}
