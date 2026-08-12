/**
 * 阶段五·2C: Knowledge Graph API 客户端封装。
 *
 * 后端端点:
 *   POST /kg/search                GraphRAG 检索 + 生成
 *   GET  /kg/concept/{id}          概念详情 + 1 跳邻居
 *   GET  /kg/study-recommendations 基于掌握度的推荐
 *   GET  /kg/path?from=&to=        两概念最短路径
 *   GET  /kg/similar-concepts/{id} 向量相似概念
 *   POST /feedback/kg-answer       用户反馈 👍/👎
 */
import client from './client'

export interface Concept {
  id: string
  name: string
  type: string
  aliases?: string[]
  definition?: string
  difficulty?: number
  confidence?: number
  subject?: string
  status?: string
  pg_kp_id?: number
}

export interface CitedConcept {
  id: string
  name: string
  type: string
}

export interface RetrievedNode {
  id: string
  name: string
  type: string
  subject: string
  pg_kp_id: number | null
  vector_score: number
  confidence: number
  mastery: { score: number; correct_rate: number; status: string } | null
}

export interface GraphSearchResult {
  answer: string
  cited: CitedConcept[]
  seeds: RetrievedNode[]
  expanded: RetrievedNode[]
  fallback: boolean
  used_token_estimate: number
}

export interface ConceptDetailResponse {
  concept: Concept
  prerequisites: CitedConcept[]
  next_concepts: CitedConcept[]
  common_mistakes: CitedConcept[]
  user_state: { score: number; correct_rate: number; status: string } | null
}

export interface StudyRecommendation {
  root_id: string
  root_name: string
  root_type: string
  weak_id: string
  weak_name: string
  weak_pg_id: number
  depth: number
}

export interface SimilarConcept {
  id: string
  name: string
  type: string
  subject?: string
  score: number
}

export interface FeedbackPayload {
  query: string
  answer: string
  cited_concepts: CitedConcept[]
  rating: -1 | 0 | 1
}

export const kgApi = {
  /** GraphRAG 问答：返回 {answer, cited, fallback, used_token_estimate}。 */
  search: (query: string) =>
    client.post<GraphSearchResult>('/kg/search', { query }),

  /** 概念详情 + 1 跳邻居（前置 + 后继 + 错因）+ 当前用户掌握度。 */
  getConcept: (id: string) =>
    client.get<ConceptDetailResponse>(`/kg/concept/${encodeURIComponent(id)}`),

  /** 基于用户薄弱 KP 的学习推荐（limit=1..20）。 */
  getStudyRecommendations: (limit = 5) =>
    client.get<StudyRecommendation[]>('/kg/study-recommendations', {
      params: { limit },
    }),

  /** 两概念最短路径（最多 6 跳）。 */
  getPath: (from: string, to: string) =>
    client.get<{ path: string[] }>('/kg/path', {
      params: { from, to },
    }),

  /** 向量相似概念（k=1..20）。 */
  getSimilarConcepts: (id: string, limit = 5) =>
    client.get<SimilarConcept[]>(`/kg/similar-concepts/${encodeURIComponent(id)}`, {
      params: { limit },
    }),

  /** 用户对 GraphRAG 回答的 👍/👎（rating=1 必传 cited_concepts）。 */
  submitFeedback: (data: FeedbackPayload) =>
    client.post('/feedback/kg-answer', data),
}