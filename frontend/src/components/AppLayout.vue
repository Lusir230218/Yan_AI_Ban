<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const navItems = [
  { name: 'dashboard', label: '工作台', icon: '📊' },
  { name: 'plans', label: '学习计划', icon: '📋' },
  { name: 'records', label: '学习记录', icon: '📝' },
  { name: 'diagnosis', label: '考研画像', icon: '👤' },
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
    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="sidebar-brand">
        <div class="brand-icon">🧠</div>
        <div class="brand-text">
          <h1>研AI伴</h1>
          <span>AI 考研备考系统</span>
        </div>
      </div>

      <nav class="sidebar-nav">
        <button
          v-for="item in navItems"
          :key="item.name"
          :class="['nav-item', { active: route.name === item.name }]"
          @click="router.push({ name: item.name })"
        >
          <span class="nav-icon">{{ item.icon }}</span>
          <span class="nav-label">{{ item.label }}</span>
        </button>
      </nav>

      <div class="sidebar-footer">
        <div class="user-info">
          <div class="user-avatar">{{ auth.user?.nickname?.charAt(0) || '?' }}</div>
          <div class="user-meta">
            <span class="user-name">{{ auth.user?.nickname || '未登录' }}</span>
            <span class="user-school">{{ auth.user?.target_school || '未设置目标' }}</span>
          </div>
        </div>
      </div>
    </aside>

    <!-- Main area -->
    <div class="main-area">
      <!-- Top header -->
      <header class="top-header">
        <h2 class="page-title">{{ pageTitle }}</h2>
        <div class="header-actions">
          <button class="btn-logout" @click="handleLogout">退出登录</button>
        </div>
      </header>

      <!-- Content -->
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

.sidebar {
  width: 260px;
  min-width: 260px;
  background: #1e293b;
  color: #e2e8f0;
  display: flex;
  flex-direction: column;
  position: sticky;
  top: 0;
  height: 100vh;
}

.sidebar-brand {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 24px 20px 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}
.brand-icon {
  width: 42px;
  height: 42px;
  background: linear-gradient(135deg, #4f46e5, #6366f1);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
}
.brand-text h1 {
  font-size: 18px;
  font-weight: 700;
  color: #fff;
  margin: 0;
  line-height: 1.2;
}
.brand-text span {
  font-size: 12px;
  color: #94a3b8;
}

.sidebar-nav {
  flex: 1;
  padding: 16px 12px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border: none;
  background: transparent;
  color: #94a3b8;
  font-size: 15px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.15s;
  text-align: left;
  width: 100%;
}
.nav-item:hover {
  background: rgba(255, 255, 255, 0.06);
  color: #e2e8f0;
}
.nav-item.active {
  background: rgba(79, 70, 229, 0.2);
  color: #a5b4fc;
  font-weight: 600;
}
.nav-icon {
  font-size: 18px;
  width: 24px;
  text-align: center;
  flex-shrink: 0;
}
.nav-label {
  white-space: nowrap;
}

.sidebar-footer {
  padding: 16px 20px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
}
.user-info {
  display: flex;
  align-items: center;
  gap: 10px;
}
.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, #4f46e5, #7c3aed);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  font-weight: 600;
  color: #fff;
  flex-shrink: 0;
}
.user-meta {
  display: flex;
  flex-direction: column;
  min-width: 0;
}
.user-name {
  font-size: 14px;
  font-weight: 500;
  color: #e2e8f0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.user-school {
  font-size: 12px;
  color: #64748b;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.top-header {
  background: #fff;
  padding: 16px 32px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e5e7eb;
  position: sticky;
  top: 0;
  z-index: 10;
}
.page-title {
  font-size: 20px;
  font-weight: 600;
  color: #1f2937;
  margin: 0;
}
.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}
.btn-logout {
  padding: 8px 16px;
  border: 1px solid #d1d5db;
  background: #fff;
  color: #6b7280;
  border-radius: 6px;
  font-size: 14px;
  cursor: pointer;
  transition: all 0.15s;
}
.btn-logout:hover {
  background: #f9fafb;
  color: #ef4444;
  border-color: #ef4444;
}

.content {
  flex: 1;
  padding: 24px 32px;
  max-width: 1200px;
  width: 100%;
}
</style>
