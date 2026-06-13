<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const phone = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function handleLogin() {
  if (!phone.value || !password.value) {
    error.value = '请填写手机号和密码'
    return
  }
  loading.value = true
  error.value = ''
  try {
    await auth.login({ phone: phone.value, password: password.value })
    router.push('/')
  } catch (err: any) {
    error.value = err.response?.data?.detail || '登录失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="login-page">
    <div class="login-card">
      <div class="brand">
        <div class="brand-icon">🧠</div>
        <h1 class="brand-title">研AI伴</h1>
        <p class="brand-sub">AI 驱动的考研学习系统</p>
      </div>

      <form class="form" @submit.prevent="handleLogin">
        <h2 class="form-title">账号登录</h2>
        <div v-if="error" class="error-msg">{{ error }}</div>

        <div class="field">
          <label>手机号</label>
          <input v-model="phone" type="tel" placeholder="请输入手机号" maxlength="11" />
        </div>

        <div class="field">
          <label>密码</label>
          <input v-model="password" type="password" placeholder="请输入密码" />
        </div>

        <button type="submit" class="btn-primary" :disabled="loading">
          {{ loading ? '登录中...' : '登录' }}
        </button>

        <p class="switch-link">
          还没有账号？<router-link to="/register">立即注册</router-link>
        </p>
      </form>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #312e81 0%, #4f46e5 50%, #6366f1 100%);
}

.login-card {
  width: 420px;
}

.brand {
  text-align: center;
  margin-bottom: 32px;
}
.brand-icon {
  width: 56px;
  height: 56px;
  background: rgba(255, 255, 255, 0.15);
  border-radius: 14px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 28px;
  margin-bottom: 12px;
  backdrop-filter: blur(4px);
}
.brand-title {
  font-size: 30px;
  font-weight: 700;
  color: #fff;
  margin: 0 0 6px;
}
.brand-sub {
  color: rgba(255, 255, 255, 0.7);
  font-size: 15px;
  margin: 0;
}

.form {
  background: #fff;
  border-radius: 12px;
  padding: 32px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.15);
}
.form-title {
  font-size: 18px;
  font-weight: 600;
  color: #1f2937;
  margin: 0 0 20px;
}

.field {
  margin-bottom: 18px;
}
.field label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: #374151;
  margin-bottom: 6px;
}
.field input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 15px;
  outline: none;
  box-sizing: border-box;
  transition: border-color 0.2s;
}
.field input:focus {
  border-color: #4f46e5;
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
}

.btn-primary {
  width: 100%;
  padding: 11px;
  background: #4f46e5;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.2s;
}
.btn-primary:hover {
  background: #4338ca;
}
.btn-primary:disabled {
  background: #a5b4fc;
  cursor: not-allowed;
}

.error-msg {
  background: #fef2f2;
  color: #dc2626;
  padding: 10px 14px;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 14px;
}

.switch-link {
  text-align: center;
  margin-top: 20px;
  color: #6b7280;
  font-size: 14px;
}
.switch-link a {
  color: #4f46e5;
  text-decoration: none;
  font-weight: 500;
}
.switch-link a:hover {
  text-decoration: underline;
}
</style>
