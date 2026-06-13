import client from './client'
import type { UserRegister, UserLogin, Token, UserResponse } from '@/types'

export const authApi = {
  register(data: UserRegister) {
    return client.post<UserResponse>('/auth/register', data)
  },
  login(data: UserLogin) {
    return client.post<Token>('/auth/login', data)
  },
}
