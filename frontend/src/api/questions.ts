import client from './client'
import type {
  QuestionResponse,
  KnowledgePointResponse,
  KnowledgePointTree,
  AnswerSubmit,
  AnswerResult,
  QuestionCreate,
} from '@/types'

export const questionApi = {
  listQuestions(params?: {
    subject?: string
    exam_variant?: string
    question_type?: string
    knowledge_point_id?: number
  }) {
    return client.get<QuestionResponse[]>('/questions', { params })
  },
  getQuestion(id: number) {
    return client.get<QuestionResponse>(`/questions/${id}`)
  },
  createQuestion(data: QuestionCreate) {
    return client.post<QuestionResponse>('/questions', data)
  },
  deleteQuestion(id: number) {
    return client.delete(`/questions/${id}`)
  },
  submitAnswer(id: number, data: AnswerSubmit) {
    return client.post<AnswerResult>(`/questions/${id}/submit`, data)
  },
  listKnowledgePoints(params?: { subject?: string; exam_variant?: string }) {
    return client.get<KnowledgePointResponse[]>('/questions/knowledge-points', { params })
  },
  getKnowledgeTree(params?: { subject?: string; exam_variant?: string }) {
    return client.get<KnowledgePointTree[]>('/questions/knowledge-points/tree', { params })
  },
}
