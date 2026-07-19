import client from './client'
import type { EncouragerMessage } from '@/types'

export const encouragerApi = {
  async getMessage(): Promise<EncouragerMessage> {
    const { data } = await client.get<EncouragerMessage>('/encourager/message')
    return data
  },

  async checkin() {
    const { data } = await client.post('/encourager/checkin')
    return data
  },
}
