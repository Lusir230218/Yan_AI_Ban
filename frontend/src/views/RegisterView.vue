<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const nickname = ref('')
const phone = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')
const success = ref(false)

async function handleRegister() {
  if (!nickname.value || !phone.value || !password.value) {
    error.value = '请填写所有字段'
    return
  }
  loading.value = true
  error.value = ''
  try {
    await auth.register({
      nickname: nickname.value,
      phone: phone.value,
      password: password.value,
    })
    success.value = true
    setTimeout(() => router.push('/login'), 1500)
  } catch (err: any) {
    error.value = err.response?.data?.detail || '注册失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="register-page">
    <div class="register-card">
      <div class="brand">
        <div class="brand-icon">🧠</div>
        <h1 class="brand-title">研AI伴</h1>
        <p class="brand-sub">创建你的备考账号</p>
      </div>

      <form class="form" @submit.prevent="handleRegister">
        <h2 class="form-title">创建账号</h2>

        <div v-if="error" class="msg error">{{ error }}</div>
        <div v-if="success" class="msg success">注册成功！即将跳转到登录页...</div>

        <div class="field">
          <label>昵称</label>
          <input v-model="nickname" placeholder="请输入昵称" maxlength="50" />
        </div>

        <div class="field">
          <label>手机号</label>
          <input v-model="phone" type="tel" placeholder="请输入手机号" maxlength="11" />
        </div>

        <div class="field">
          <label>密码</label>
          <input v-model="password" type="password" placeholder="请设置密码（至少6位）" />
        </div>

        <button type="submit" class="btn-primary" :disabled="loading">
          {{ loading ? '注册中...' : '注册' }}
        </button>
      </form>

      <p class="switch-link">
        已有账号？<router-link to="/login">去登录</router-link>
      </p>
    </div>
  </div>
</template>

<style scoped>
.register-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #312e81 0%, #4f46e5 50%, #6366f1 100%);
}
.register-card {
  width: 420px;
}
.brand {
  text-align: center;
  margin-bottom: 28px;
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
  padding: 28px 32px;
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
}
.btn-primary:hover {
  background: #4338ca;
}
.btn-primary:disabled {
  background: #a5b4fc;
  cursor: not-allowed;
}
.msg {
  padding: 10px 14px;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 14px;
}
.msg.error {
  background: #fef2f2;
  color: #dc2626;
}
.msg.success {
  background: #f0fdf4;
  color: #16a34a;
}
.switch-link {
  text-align: center;
  margin-top: 20px;
  color: rgba(255, 255, 255, 0.7);
  font-size: 14px;
}
.switch-link a {
  color: #fff;
  text-decoration: none;
  font-weight: 500;
}
.switch-link a:hover {
  text-decoration: underline;
}
</style>
