<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { Iphone, Lock } from '@element-plus/icons-vue'
import ThreeBackground from '@/components/ThreeBackground.vue'
import logoSvg from '@/assets/logo.svg'

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
  loading.value = true; error.value = ''
  try {
    await auth.login({ phone: phone.value, password: password.value })
    router.push('/')
  } catch (err: any) {
    error.value = err.response?.data?.detail || '登录失败，请重试'
  } finally { loading.value = false }
}
</script>

<template>
  <div class="login-page">
    <ThreeBackground :particle-count="100" color="#a78bfa" :speed="0.15" />
    <div class="login-card">
      <div class="brand">
        <div class="brand-icon"><img :src="logoSvg" alt="logo" /></div>
        <h1 class="brand-title">研AI伴</h1>
        <p class="brand-sub">AI 驱动的考研学习系统</p>
      </div>

      <el-card shadow="always" class="form-card">
        <h2 class="form-title">账号登录</h2>
        <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="error-box" />

        <el-form @submit.prevent="handleLogin" label-position="top">
          <el-form-item label="手机号">
            <el-input v-model="phone" placeholder="请输入手机号" :prefix-icon="Iphone" maxlength="11" size="large" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="password" type="password" placeholder="请输入密码" :prefix-icon="Lock" show-password size="large" />
          </el-form-item>
          <el-button type="primary" size="large" :loading="loading" native-type="submit" class="login-btn">登录</el-button>
        </el-form>

        <p class="switch-link">还没有账号？<router-link to="/register">立即注册</router-link></p>
      </el-card>
    </div>
  </div>
</template>

<style scoped>
.login-page {
  min-height: 100vh; display: flex; align-items: center; justify-content: center;
  background: #0f0a1e;
  position: relative; overflow: hidden;
}
.login-card { position: relative; z-index: 1; }
.login-card { width: 420px; position: relative; z-index: 1; }
.brand { text-align: center; margin-bottom: 32px; }
.brand-icon {
  margin-bottom: 14px; display: inline-flex; align-items: center; justify-content: center;
}
.brand-icon img { height: 56px; width: auto; }
.brand-title { font-size: 32px; font-weight: 800; color: #fff; margin: 0 0 6px; }
.brand-sub { color: rgba(255,255,255,0.65); font-size: 15px; margin: 0; }
.form-card { border-radius: 16px; }
.form-card :deep(.el-card__body) { padding: 36px; }
.form-title { font-size: 18px; font-weight: 700; color: #1f2937; margin: 0 0 20px; }
.error-box { margin-bottom: 16px; }
.login-btn { width: 100%; margin-top: 8px; }
.switch-link { text-align: center; margin-top: 24px; color: #6b7280; font-size: 14px; }
.switch-link a { color: #4f46e5; font-weight: 500; text-decoration: none; }
.switch-link a:hover { text-decoration: underline; }
</style>
