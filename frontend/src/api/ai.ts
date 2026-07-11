import client from './client'
import type { AiSolveResponse } from '@/types'

export async function aiSolve(params: {
  image?: File
  text?: string
  multi_modal?: boolean
  subject?: string
  exam_variant?: string
}): Promise<AiSolveResponse> {
  const form = new FormData()
  if (params.image) form.append('image', params.image)
  if (params.text) form.append('text', params.text)
  if (params.multi_modal) form.append('multi_modal', 'true')
  if (params.subject) form.append('subject', params.subject)
  if (params.exam_variant) form.append('exam_variant', params.exam_variant)

  const { data } = await client.post<AiSolveResponse>('/ai-solve', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000,
  })
  return data
}