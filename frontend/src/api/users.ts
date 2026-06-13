import client from './client'
import type { UserResponse, UserDiagnosis } from '@/types'

export const usersApi = {
  getMe() {
    return client.get<UserResponse>('/users/me')
  },
  updateDiagnosis(data: UserDiagnosis) {
    return client.put<UserResponse>('/users/me/diagnosis', data)
  },
}
