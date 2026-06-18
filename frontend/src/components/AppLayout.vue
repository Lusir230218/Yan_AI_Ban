<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import logoSvg from '@/assets/logo.svg'
import {
  Monitor, Notebook, Document, Clock, User, SwitchButton
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const navItems = [
  { name: 'dashboard', label: '工作台', icon: Monitor },
  { name: 'practice', label: '题库练习', icon: Notebook },
  { name: 'plans', label: '学习计划', icon: Document },
  { name: 'records', label: '学习记录', icon: Clock },
  { name: 'diagnosis', label: '考研画像', icon: User },
]

const pageTitle = computed(() => {
  const item = navItems.find(n => n.name === route.name)
  return item?.label || '研AI伴'
})

function handleLogout() {
  auth.logout()
  router.push('/login')
}
</script>

<template>
  <div class="app-layout">
    <aside class="sidebar">
      <div class="sidebar-brand">
        <div class="brand-logo">
          <img :src="logoSvg" alt="logo" height="32" />
        </div>
        <div class="brand-info">
          <h1>研AI伴</h1>
          <span>考研智能备考</span>
        </div>
      </div>

      <nav class="sidebar-nav">
        <button
          v-for="item in navItems"
          :key="item.name"
          :class="['nav-item', { active: route.name === item.name }]"
          @click="router.push({ name: item.name })"
        >
          <el-icon :size="18"><component :is="item.icon" /></el-icon>
          <span>{{ item.label }}</span>
          <span v-if="route.name === item.name" class="nav-indicator" />
        </button>
      </nav>

      <div class="sidebar-footer">
        <div class="user-card">
          <el-avatar :size="36">{{ auth.user?.nickname?.charAt(0) || '?' }}</el-avatar>
          <div class="user-info">
            <span class="user-name">{{ auth.user?.nickname || '未登录' }}</span>
            <span class="user-school">{{ auth.user?.target_school || '未设置目标' }}</span>
          </div>
        </div>
      </div>
    </aside>

    <div class="main-area">
      <header class="top-header">
        <h2 class="page-title">{{ pageTitle }}</h2>
        <div class="header-actions">
          <slot name="header-actions" />
          <el-button
            :icon="SwitchButton"
            text
            size="small"
            @click="handleLogout"
          >退出登录</el-button>
        </div>
      </header>

      <main class="content">
        <slot />
      </main>
    </div>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
  background: #f0f2f5;
}

/* ── Sidebar ── */
.sidebar {
  width: 260px;
  min-width: 260px;
  background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
  color: #e2e8f0;
  display: flex;
  flex-direction: column;
  position: sticky;
  top: 0;
  height: 100vh;
  z-index: 20;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 24px 20px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}
.brand-logo {
  display: flex;
  align-items: center;
}
.brand-logo img {
  height: 36px;
  width: auto;
}
.brand-info h1 {
  font-size: 19px;
  font-weight: 700;
  color: #fff;
  margin: 0;
  line-height: 1.3;
}
.brand-info span {
  font-size: 12px;
  color: #8892b0;
}

/* ── Nav ── */
.sidebar-nav {
  flex: 1;
  padding: 20px 12px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 13px 16px;
  border: none;
  background: transparent;
  color: #8892b0;
  font-size: 14px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;
  width: 100%;
  position: relative;
}
.nav-item:hover {
  background: rgba(255, 255, 255, 0.05);
  color: #ccd6f6;
}
.nav-item.active {
  background: rgba(102, 126, 234, 0.15);
  color: #a8b5f0;
  font-weight: 600;
}
.nav-indicator {
  position: absolute;
  right: -4px;
  top: 50%;
  transform: translateY(-50%);
  width: 3px;
  height: 20px;
  background: #667eea;
  border-radius: 2px;
}

/* ── Footer ── */
.sidebar-footer {
  padding: 16px 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
}
.user-card {
  display: flex;
  align-items: center;
  gap: 10px;
}
.user-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.user-name {
  font-size: 14px;
  font-weight: 500;
  color: #ccd6f6;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.user-school {
  font-size: 11px;
  color: #64748b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* ── Main ── */
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.top-header {
  background: rgba(255, 255, 255, 0.8);
  backdrop-filter: blur(20px);
  padding: 14px 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid rgba(0, 0, 0, 0.05);
  position: sticky;
  top: 0;
  z-index: 10;
}
.page-title {
  font-size: 19px;
  font-weight: 700;
  color: #1f2937;
  margin: 0;
  background: linear-gradient(135deg, #667eea, #764ba2);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.content {
  flex: 1;
  padding: 24px 32px;
  max-width: 1200px;
  width: 100%;
}
</style>
