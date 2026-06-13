import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { UserResponse, UserLogin, UserRegister, UserDiagnosis } from '@/types'
import { authApi } from '@/api/auth'
import { usersApi } from '@/api/users'

export const useAuthStore = defineStore('auth', () => {
  const token = ref(localStorage.getItem('token') || '')
  const user = ref<UserResponse | null>(null)

  async function login(data: UserLogin) {
    const res = await authApi.login(data)
    token.value = res.data.access_token
    localStorage.setItem('token', res.data.access_token)
    await fetchUser()
  }

  async function register(data: UserRegister) {
    const res = await authApi.register(data)
    return res.data
  }

  async function fetchUser() {
    try {
      const res = await usersApi.getMe()
      user.value = res.data
    } catch {
      logout()
    }
  }

  async function updateDiagnosis(data: UserDiagnosis) {
    const res = await usersApi.updateDiagnosis(data)
    user.value = res.data
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
  }

  return { token, user, login, register, fetchUser, updateDiagnosis, logout }
})
