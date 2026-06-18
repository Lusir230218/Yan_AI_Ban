<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { Iphone, Lock, User } from '@element-plus/icons-vue'
import ThreeBackground from '@/components/ThreeBackground.vue'
import logoSvg from '@/assets/logo.svg'

const router = useRouter()
const auth = useAuthStore()
const nickname = ref('')
const phone = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')
const success = ref(false)

async function handleRegister() {
  if (!nickname.value || !phone.value || !password.value) { error.value = '请填写所有字段'; return }
  loading.value = true; error.value = ''
  try {
    await auth.register({ nickname: nickname.value, phone: phone.value, password: password.value })
    success.value = true; setTimeout(() => router.push('/login'), 1500)
  } catch (err: any) { error.value = err.response?.data?.detail || '注册失败，请重试' }
  finally { loading.value = false }
}
</script>

<template>
  <div class="page">
    <ThreeBackground :particle-count="80" color="#f59e0b" :speed="0.15" />
    <div class="card">
      <div class="brand">
        <div class="brand-icon"><img :src="logoSvg" alt="logo" /></div>
        <h1 class="brand-title">研AI伴</h1>
        <p class="brand-sub">创建你的备考账号</p>
      </div>
      <el-card shadow="always" class="form-card">
        <h2 class="form-title">创建账号</h2>
        <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="mb" />
        <el-alert v-if="success" title="注册成功！即将跳转到登录页..." type="success" show-icon :closable="false" class="mb" />
        <el-form @submit.prevent="handleRegister" label-position="top">
          <el-form-item label="昵称">
            <el-input v-model="nickname" placeholder="请输入昵称" :prefix-icon="User" maxlength="50" size="large" />
          </el-form-item>
          <el-form-item label="手机号">
            <el-input v-model="phone" placeholder="请输入手机号" :prefix-icon="Iphone" maxlength="11" size="large" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="password" type="password" placeholder="请设置密码（至少6位）" :prefix-icon="Lock" show-password size="large" />
          </el-form-item>
          <el-button type="primary" size="large" native-type="submit" :loading="loading" class="full-btn">注册</el-button>
        </el-form>
      </el-card>
      <p class="switch-link">已有账号？<router-link to="/login">去登录</router-link></p>
    </div>
  </div>
</template>

<style scoped>
.page {
  min-height: 100vh; display: flex; align-items: center; justify-content: center;
  background: #0f0a1e;
}
.card { width: 420px; position: relative; z-index: 1; }
.brand { text-align: center; margin-bottom: 28px; }
.brand-icon { margin-bottom: 14px; display: inline-flex; align-items: center; justify-content: center; }
.brand-icon img { height: 56px; width: auto; }
.brand-title { font-size: 32px; font-weight: 800; color: #fff; margin: 0 0 6px; }
.brand-sub { color: rgba(255,255,255,0.65); font-size: 15px; margin: 0; }
.form-card { border-radius: 16px; }
.form-card :deep(.el-card__body) { padding: 32px; }
.form-title { font-size: 18px; font-weight: 700; color: #1f2937; margin: 0 0 20px; }
.mb { margin-bottom: 16px; }
.full-btn { width: 100%; margin-top: 8px; }
.switch-link { text-align: center; margin-top: 20px; color: rgba(255,255,255,0.7); font-size: 14px; }
.switch-link a { color: #fff; font-weight: 500; text-decoration: none; }
.switch-link a:hover { text-decoration: underline; }
</style>
