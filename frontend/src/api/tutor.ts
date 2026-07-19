import client from './client'
import type { TutorStartResponse, TutorContinueResponse, TutorSessionResponse, TutorSessionListItem } from '@/types'

export const tutorApi = {
  async start(params: {
    image?: File
    text?: string
    multi_modal?: boolean
    subject?: string
    exam_variant?: string
  }): Promise<TutorStartResponse> {
    const form = new FormData()
    if (params.image) form.append('image', params.image)
    if (params.text) form.append('text', params.text)
    if (params.multi_modal) form.append('multi_modal', 'true')
    if (params.subject) form.append('subject', params.subject)
    if (params.exam_variant) form.append('exam_variant', params.exam_variant)

    const { data } = await client.post<TutorStartResponse>('/ai-solve/tutor', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120000,
    })
    return data
  },

  async continue_(sessionId: number, userInput: string): Promise<TutorContinueResponse> {
    const { data } = await client.post<TutorContinueResponse>(
      `/ai-solve/tutor/${sessionId}/continue`,
      { user_input: userInput },
      { timeout: 120000 },
    )
    return data
  },

  async getSession(sessionId: number): Promise<TutorSessionResponse> {
    const { data } = await client.get<TutorSessionResponse>(`/ai-solve/tutor/${sessionId}`)
    return data
  },

  async list(): Promise<TutorSessionListItem[]> {
    const { data } = await client.get<TutorSessionListItem[]>('/ai-solve/tutor')
    return data
  },

  async reveal(sessionId: number): Promise<TutorContinueResponse> {
    const { data } = await client.post<TutorContinueResponse>(
      `/ai-solve/tutor/${sessionId}/reveal`,
      undefined,
      { timeout: 120000 },
    )
    return data
  },
}
