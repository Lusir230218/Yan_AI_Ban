<script setup lang="ts">
import { onMounted, computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { studyApi } from '@/api/study'
import type { StudyPlanResponse, StudyRecordResponse } from '@/types'
import AppLayout from '@/components/AppLayout.vue'

const auth = useAuthStore()
const router = useRouter()

const plans = ref<StudyPlanResponse[]>([])
const records = ref<StudyRecordResponse[]>([])
const loading = ref(true)

onMounted(async () => {
  if (!auth.user) await auth.fetchUser()
  try {
    const [plansRes, recordsRes] = await Promise.all([
      studyApi.listPlans(),
      studyApi.listRecords(),
    ])
    plans.value = plansRes.data
    records.value = recordsRes.data
  } catch {
    // silently fail
  } finally {
    loading.value = false
  }
})

function greet() {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'
  if (h < 9) return '早上好'
  if (h < 12) return '上午好'
  if (h < 14) return '中午好'
  if (h < 18) return '下午好'
  return '晚上好'
}

const recentRecords = computed(() => records.value.slice(0, 5))
</script>

<template>
  <AppLayout>
    <div class="dashboard">
      <!-- Welcome banner -->
      <div class="welcome-banner">
        <div class="welcome-text">
          <h2>{{ greet() }}，{{ auth.user?.nickname || '同学' }}</h2>
          <p v-if="auth.user?.target_school">
            目标：{{ auth.user.target_school }}
            <template v-if="auth.user?.target_major"> · {{ auth.user.target_major }}</template>
          </p>
          <p v-else class="hint">
            <router-link to="/diagnosis">填写考研画像，获取个性化学习方案 →</router-link>
          </p>
        </div>
        <div class="welcome-emoji">🎯</div>
      </div>

      <!-- Stats -->
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-icon stat-icon-plan">📋</div>
          <div class="stat-body">
            <span class="stat-num">{{ plans.length }}</span>
            <span class="stat-label">学习计划</span>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon stat-icon-record">📝</div>
          <div class="stat-body">
            <span class="stat-num">{{ records.length }}</span>
            <span class="stat-label">学习记录</span>
          </div>
        </div>
        <div class="stat-card">
          <div class="stat-icon stat-icon-streak">🔥</div>
          <div class="stat-body">
            <span class="stat-num">{{ records.length > 0 ? '活跃' : '暂无' }}</span>
            <span class="stat-label">学习状态</span>
          </div>
        </div>
      </div>

      <div v-if="loading" class="loading-state">加载中...</div>

      <template v-else>
        <!-- Two-column layout -->
        <div class="content-grid">
          <!-- Recent records -->
          <section class="card">
            <div class="card-header">
              <h3>最近学习</h3>
              <router-link v-if="records.length" to="/records" class="card-more">查看全部 →</router-link>
            </div>
            <div v-if="recentRecords.length === 0" class="empty-state">
              <p>还没有学习记录</p>
              <router-link to="/records" class="btn-link">开始学习 →</router-link>
            </div>
            <div v-for="r in recentRecords" :key="r.id" class="record-row">
              <span class="tag-subject">{{ r.subject }}</span>
              <span :class="['tag-result', r.is_correct === null ? '' : r.is_correct ? 'correct' : 'wrong']">
                {{ r.is_correct === null ? '待批改' : r.is_correct ? '正确' : '错误' }}
              </span>
              <span class="record-duration">{{ Math.floor(r.duration_seconds / 60) }} 分钟</span>
              <span class="record-date">{{ r.created_at?.slice(0, 10) }}</span>
            </div>
          </section>

          <!-- Study plans -->
          <section class="card">
            <div class="card-header">
              <h3>学习计划</h3>
              <router-link v-if="plans.length" to="/plans" class="card-more">查看全部 →</router-link>
            </div>
            <div v-if="plans.length === 0" class="empty-state">
              <p>还没有学习计划</p>
              <router-link to="/plans" class="btn-link">创建计划 →</router-link>
            </div>
            <div v-for="p in plans.slice(0, 5)" :key="p.id" class="plan-row">
              <div class="plan-info">
                <span class="plan-name">{{ p.phase }}</span>
                <span class="plan-dates">{{ p.start_date }} ~ {{ p.end_date }}</span>
              </div>
              <span :class="['plan-badge', p.status]">
                {{ p.status === 'active' ? '进行中' : '已完成' }}
              </span>
            </div>
          </section>
        </div>
      </template>
    </div>
  </AppLayout>
</template>

<style scoped>
.dashboard {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.welcome-banner {
  background: linear-gradient(135deg, #4f46e5, #6366f1);
  color: #fff;
  border-radius: 12px;
  padding: 24px 28px;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}
.welcome-text h2 {
  font-size: 22px;
  font-weight: 700;
  margin: 0 0 6px;
}
.welcome-text p {
  font-size: 15px;
  margin: 0;
  opacity: 0.9;
}
.hint a {
  color: #fff;
  text-decoration: underline;
  opacity: 0.85;
}
.hint a:hover {
  opacity: 1;
}
.welcome-emoji {
  font-size: 40px;
  flex-shrink: 0;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}
.stat-card {
  background: #fff;
  border-radius: 10px;
  padding: 20px;
  display: flex;
  align-items: center;
  gap: 16px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}
.stat-icon {
  width: 48px;
  height: 48px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  flex-shrink: 0;
}
.stat-icon-plan { background: #eef2ff; }
.stat-icon-record { background: #f0fdf4; }
.stat-icon-streak { background: #fff7ed; }
.stat-body {
  display: flex;
  flex-direction: column;
}
.stat-num {
  font-size: 24px;
  font-weight: 700;
  color: #1f2937;
  line-height: 1.2;
}
.stat-label {
  font-size: 13px;
  color: #6b7280;
}
.content-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.card {
  background: #fff;
  border-radius: 10px;
  padding: 20px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f3f4f6;
}
.card-header h3 {
  font-size: 16px;
  font-weight: 600;
  margin: 0;
}
.card-more {
  font-size: 13px;
  color: #4f46e5;
  font-weight: 500;
}
.card-more:hover {
  text-decoration: underline;
}
.record-row {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid #f9fafb;
  font-size: 14px;
}
.record-row:last-child {
  border-bottom: none;
}
.tag-subject {
  background: #eef2ff;
  color: #4f46e5;
  padding: 2px 10px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 500;
}
.tag-result.correct { color: #16a34a; font-weight: 500; }
.tag-result.wrong { color: #dc2626; font-weight: 500; }
.record-duration {
  color: #6b7280;
  margin-left: auto;
}
.record-date {
  color: #9ca3af;
  font-size: 13px;
}
.plan-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 0;
  border-bottom: 1px solid #f9fafb;
}
.plan-row:last-child {
  border-bottom: none;
}
.plan-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.plan-name {
  font-weight: 500;
  font-size: 14px;
}
.plan-dates {
  font-size: 13px;
  color: #6b7280;
}
.plan-badge {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 10px;
  font-weight: 500;
}
.plan-badge.active {
  background: #dcfce7;
  color: #16a34a;
}
.plan-badge.completed {
  background: #f3f4f6;
  color: #6b7280;
}
.loading-state {
  text-align: center;
  color: #9ca3af;
  padding: 60px 0;
}
.empty-state {
  text-align: center;
  padding: 32px 0;
  color: #9ca3af;
}
.empty-state p {
  margin-bottom: 12px;
}
.btn-link {
  color: #4f46e5;
  font-weight: 500;
}
.btn-link:hover {
  text-decoration: underline;
}
</style>
