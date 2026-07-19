import client from './client'
import type { EvaluationPrediction } from '@/types'

export const evaluationApi = {
  async predict(): Promise<EvaluationPrediction> {
    const { data } = await client.post<EvaluationPrediction>('/evaluation/predict')
    return data
  },

  async getReports() {
    const { data } = await client.get('/evaluation/reports')
    return data
  },

  async getReport(id: number) {
    const { data } = await client.get(`/evaluation/reports/${id}`)
    return data
  },
}
