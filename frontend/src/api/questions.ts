import client from './client'
import type { QuestionResponse, AnswerSubmit, AnswerResult, QuestionCreate } from '@/types'

export const questionApi = {
  listQuestions(params?: { subject?: string; knowledge_point_id?: number }) {
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
}
