import { describe, expect, it } from 'vitest'

import {
  formatDate,
  formatDuration,
  formatShortDuration,
  formatSize,
  getReportTitle,
  getReportTone,
  parseReportName,
  parseRunLabel,
  splitTestName,
  statusTone,
} from './reports'
import type { Report } from '../types/reports'

describe('formatDate', () => {
  it('returns placeholder for null or invalid values', () => {
    expect(formatDate(null)).toBe('-')
    expect(formatDate('not-a-date')).toBe('-')
  })

  it('formats valid dates', () => {
    expect(formatDate('2024-03-05T10:20:00')).toMatch(/2024/)
  })
})

describe('formatSize', () => {
  it('formats zero bytes', () => {
    expect(formatSize(0)).toBe('0 B')
  })

  it('scales to larger units', () => {
    expect(formatSize(2048)).toBe('2.0 KB')
    expect(formatSize(5 * 1024 * 1024)).toBe('5.0 MB')
  })
})

describe('formatDuration', () => {
  it('returns placeholder for missing values', () => {
    expect(formatDuration(null)).toBe('-')
    expect(formatDuration(undefined)).toBe('-')
  })

  it('formats hours, minutes and seconds', () => {
    expect(formatDuration(0)).toBe('00:00:00')
    expect(formatDuration(61_000)).toBe('00:01:01')
    expect(formatDuration(3_661_000)).toBe('01:01:01')
  })
})

describe('getReportTitle', () => {
  const base: Report = {
    id: 'report-id',
    name: '',
    created_at: '2024-03-05T10:20:00',
    size: 0,
    entry_path: null,
  }

  it('prefers explicit name', () => {
    expect(getReportTitle({ ...base, name: 'Nightly' })).toBe('Nightly')
  })

  it('falls back to entry path tail', () => {
    expect(getReportTitle({ ...base, entry_path: 'runs/2024-03-05/index.html' })).toBe('index.html')
  })

  it('falls back to id', () => {
    expect(getReportTitle(base)).toBe('report-id')
  })
})

describe('parseRunLabel', () => {
  it('extracts day and time from Allure report names', () => {
    expect(parseRunLabel('Allure Report 2026-09-22_11-13 zpirozhenko')).toEqual({ day: '22.09', time: '11:13' })
    expect(parseRunLabel('2026-09-15 18:57')).toEqual({ day: '15.09', time: '18:57' })
  })

  it('falls back to the raw label', () => {
    expect(parseRunLabel('nightly')).toEqual({ day: 'nightly', time: '' })
  })
})

describe('splitTestName', () => {
  it('splits on # first', () => {
    expect(splitTestName('Claims.Tests.test_notify_claim#test_02_sign')).toEqual({
      module: 'Claims.Tests.test_notify_claim',
      method: 'test_02_sign',
    })
  })

  it('falls back to the last dot and to the whole name', () => {
    expect(splitTestName('pkg.mod.test_a')).toEqual({ module: 'pkg.mod', method: 'test_a' })
    expect(splitTestName('test_a')).toEqual({ module: '', method: 'test_a' })
  })
})

describe('statusTone', () => {
  it('normalizes known statuses and groups the rest', () => {
    expect(statusTone(' Broken ')).toBe('broken')
    expect(statusTone('skipped')).toBe('other')
    expect(statusTone(undefined)).toBe('other')
  })
})

describe('formatShortDuration', () => {
  it('picks a unit by magnitude', () => {
    expect(formatShortDuration(null)).toBe('-')
    expect(formatShortDuration(850)).toBe('850 ms')
    expect(formatShortDuration(7941)).toBe('7.9 s')
    expect(formatShortDuration(125_000)).toBe('2 m 05 s')
    expect(formatShortDuration(5_239_578)).toBe('1 h 27 m')
  })
})

describe('parseReportName', () => {
  it('extracts date, time and author', () => {
    expect(parseReportName('Allure Report 2026-09-22_11-13 zpirozhenko')).toEqual({
      date: '22.09.2026',
      time: '11:13',
      user: 'zpirozhenko',
    })
    expect(parseReportName('Отчёт 2026-09-25_12-30')).toEqual({ date: '25.09.2026', time: '12:30', user: null })
  })

  it('returns null for free-form names', () => {
    expect(parseReportName('nightly regression')).toBeNull()
  })
})

describe('getReportTone', () => {
  const base = { id: '1', name: 'r', created_at: '', size: 0 }
  it('prefers explicit status, then stats', () => {
    expect(getReportTone({ ...base, status: 'Broken' })).toBe('broken')
    expect(getReportTone({ ...base, stats: { total: 3, passed: 2, failed: 1, flaky: 0, broken: 0 } })).toBe('failed')
    expect(getReportTone({ ...base, stats: { total: 0, passed: 0, failed: 0, flaky: 0, broken: 0 } })).toBe('other')
  })
})
