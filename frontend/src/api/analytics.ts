import client from './client'

export interface KPMastery {
  kp_id: number
  name: string
  code: string
  level: number
  chapter: string | null
  section: string | null
  score: number
  correct_rate: number
  last_reviewed: string | null
}

export interface TopMistake {
  name: string
  times: number
  kp_count: number
}

export interface KPWeak extends KPMastery {
  error_count: number
  last_error_at: string | null
  difficulty: number
  mastery_score: number | null
  top_mistakes: TopMistake[]
}

export interface TimelinePoint {
  captured_at: string
  score: number
  delta: number | null
}

export interface MistakeSummaryItem {
  mistake_name: string
  times: number
  first_at: string
  last_at: string
  kp_count: number
}

export const analyticsApi = {
  getUserMastery: () =>
    client.get<Record<string, KPMastery[]>>('/analytics/user-mastery'),
  getWeakPoints: (limit = 10) =>
    client.get<KPWeak[]>('/analytics/weak-points', { params: { limit } }),
  getMasteryTimeline: (kp_id: number, days = 30) =>
    client.get<TimelinePoint[]>('/analytics/mastery-timeline', { params: { kp_id, days } }),
  getMistakeSummary: (subject?: string) =>
    client.get<MistakeSummaryItem[]>('/analytics/mistake-summary', {
      params: subject ? { subject } : {},
    }),
}
