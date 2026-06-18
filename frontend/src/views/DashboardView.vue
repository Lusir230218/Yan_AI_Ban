<script setup lang="ts">
import { onMounted, computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { studyApi } from '@/api/study'
import type { StudyPlanResponse, StudyRecordResponse } from '@/types'
import AppLayout from '@/components/AppLayout.vue'
import { TrendCharts, DataAnalysis, Calendar, Trophy } from '@element-plus/icons-vue'
import ThreeBackground from '@/components/ThreeBackground.vue'

const auth = useAuthStore()
const router = useRouter()

const plans = ref<StudyPlanResponse[]>([])
const records = ref<StudyRecordResponse[]>([])
const loading = ref(true)

onMounted(async () => {
  if (!auth.user) await auth.fetchUser()
  try {
    const [plansRes, recordsRes] = await Promise.all([
      studyApi.listPlans(), studyApi.listRecords(),
    ])
    plans.value = plansRes.data; records.value = recordsRes.data
  } catch { /* skip */ }
  finally { loading.value = false }
})

function greet() {
  const h = new Date().getHours()
  if (h < 6) return '夜深了'; if (h < 9) return '早上好'
  if (h < 12) return '上午好'; if (h < 14) return '中午好'
  if (h < 18) return '下午好'; return '晚上好'
}

const correctCount = computed(() => records.value.filter(r => r.is_correct).length)
const accuracy = computed(() =>
  records.value.filter(r => r.is_correct !== null).length > 0
    ? Math.round((correctCount.value / records.value.filter(r => r.is_correct !== null).length) * 100)
    : 0
)
const todayRecords = computed(() =>
  records.value.filter(r => r.created_at?.slice(0, 10) === new Date().toISOString().slice(0, 10))
)
const recentRecords = computed(() => records.value.slice(0, 6))
</script>

<template>
  <AppLayout>
    <div class="dashboard">
      <el-skeleton :loading="loading" animated :count="4">
        <div class="hero-banner">
          <div class="hero-three-bg">
            <ThreeBackground :particle-count="60" color="#a78bfa" :speed="0.1" :connect-distance="1.2" />
          </div>
          <div class="hero-left">
            <div class="hero-greeting">
              <span class="greeting-wave">👋</span>
              <span>{{ greet() }}，{{ auth.user?.nickname || '同学' }}</span>
            </div>
            <h2 class="hero-motto">每一天的努力，都在靠近你的目标</h2>
            <div v-if="auth.user?.target_school" class="hero-target">
              <el-tag effect="dark" type="primary" size="large" round>
                🎯 {{ auth.user.target_school }}<template v-if="auth.user?.target_major"> · {{ auth.user.target_major }}</template>
              </el-tag>
            </div>
            <router-link v-else to="/diagnosis" class="hero-cta">
              <el-button type="primary" size="large" round>完善考研画像 →</el-button>
            </router-link>
          </div>
          <div class="hero-right">
            <div class="countdown-ring">
              <el-progress type="dashboard" :percentage="68" :color="'#a78bfa'">
                <template #default>
                  <span class="progress-label">距考研</span>
                  <span class="progress-days">183 天</span>
                </template>
              </el-progress>
            </div>
          </div>
        </div>

        <div class="stats-row">
          <el-card v-for="s in [
            { label: '学习计划', val: plans.length, icon: Calendar, color: '#4f46e5', bg: '#eef2ff' },
            { label: '做题记录', val: records.length, icon: TrendCharts, color: '#059669', bg: '#ecfdf5' },
            { label: '今日完成', val: todayRecords.length, icon: DataAnalysis, color: '#d97706', bg: '#fffbeb' },
            { label: '正确率', val: accuracy + '%', icon: Trophy, color: '#dc2626', bg: '#fef2f2' },
          ]" :key="s.label" class="stat-card" shadow="hover">
            <div class="stat-inner">
              <div class="stat-icon-box" :style="{ background: s.bg }">
                <el-icon :size="22" :color="s.color"><component :is="s.icon" /></el-icon>
              </div>
              <div class="stat-info">
                <span class="stat-val" :style="{ color: s.color }">{{ s.val }}</span>
                <span class="stat-label">{{ s.label }}</span>
              </div>
            </div>
          </el-card>
        </div>

        <div class="content-cols">
          <el-card shadow="hover">
            <template #header>
              <div class="card-hd">
                <span>最近学习</span>
                <router-link v-if="records.length" to="/records" class="link">全部 →</router-link>
              </div>
            </template>
            <el-empty v-if="records.length === 0" description="暂无学习记录" :image-size="80" />
            <div v-for="r in recentRecords" :key="r.id" class="row-item">
              <el-tag size="small">{{ r.subject }}</el-tag>
              <el-tag size="small" :type="r.is_correct === null ? 'info' : r.is_correct ? 'success' : 'danger'">
                {{ r.is_correct === null ? '待批改' : r.is_correct ? '正确' : '错误' }}
              </el-tag>
              <span class="row-time">{{ r.created_at?.slice(0, 10) }}</span>
            </div>
          </el-card>

          <el-card shadow="hover">
            <template #header>
              <div class="card-hd">
                <span>学习计划</span>
                <router-link v-if="plans.length" to="/plans" class="link">全部 →</router-link>
              </div>
            </template>
            <el-empty v-if="plans.length === 0" description="暂无学习计划" :image-size="80" />
            <div v-for="p in plans.slice(0, 5)" :key="p.id" class="row-item">
              <span class="plan-phase">{{ p.phase }}</span>
              <el-tag size="small" :type="p.status === 'active' ? 'success' : 'info'">
                {{ p.status === 'active' ? '进行中' : '已完成' }}
              </el-tag>
              <span class="row-time">{{ p.start_date }} ~ {{ p.end_date }}</span>
            </div>
          </el-card>
        </div>
      </el-skeleton>
    </div>
  </AppLayout>
</template>

<style scoped>
.dashboard { display: flex; flex-direction: column; gap: 20px; }

.hero-banner {
  background: linear-gradient(135deg, #1e1b4b 0%, #312e81 40%, #4c1d95 100%);
  color: #fff; border-radius: 20px; padding: 36px 40px;
  display: flex; justify-content: space-between; align-items: center;
  position: relative; overflow: hidden;
}
.hero-three-bg { position: absolute; inset: 0; z-index: 0; opacity: 0.4; border-radius: 20px; overflow: hidden; }
.hero-three-bg :deep(.three-bg) { position: absolute; }
.hero-banner::after {
  content: ''; position: absolute; top: -60px; right: -40px;
  width: 240px; height: 240px;
  background: radial-gradient(circle, rgba(167,139,250,0.3) 0%, transparent 70%);
  border-radius: 50%;
}
.hero-left { position: relative; z-index: 1; }
.hero-greeting { font-size: 16px; opacity: 0.85; margin-bottom: 8px; display: flex; align-items: center; gap: 8px; }
.greeting-wave { font-size: 24px; }
.hero-motto { font-size: 26px; font-weight: 800; margin: 0 0 16px; letter-spacing: -0.5px; }
.hero-target { margin-bottom: 12px; }
.hero-cta { display: inline-block; }
.hero-right { position: relative; z-index: 1; }
.countdown-ring { text-align: center; }
.progress-label { font-size: 12px; color: #a5b4fc; }
.progress-days { font-size: 20px; font-weight: 800; color: #fff; }

.stats-row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; }
.stat-card :deep(.el-card__body) { padding: 20px; }
.stat-inner { display: flex; align-items: center; gap: 16px; }
.stat-icon-box {
  width: 48px; height: 48px; border-radius: 14px;
  display: flex; align-items: center; justify-content: center;
}
.stat-info { display: flex; flex-direction: column; }
.stat-val { font-size: 28px; font-weight: 800; line-height: 1.1; }
.stat-label { font-size: 13px; color: #6b7280; }

.content-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
.card-hd { display: flex; justify-content: space-between; align-items: center; font-weight: 600; }
.link { font-size: 13px; color: #4f46e5; font-weight: 500; }
.row-item {
  display: flex; align-items: center; gap: 10px;
  padding: 12px 0; border-bottom: 1px solid #f3f4f6; font-size: 14px;
}
.row-item:last-child { border-bottom: none; }
.row-time { margin-left: auto; color: #9ca3af; font-size: 13px; }
.plan-phase { font-weight: 500; }
</style>
