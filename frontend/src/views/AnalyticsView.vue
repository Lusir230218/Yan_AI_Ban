<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { analyticsApi, type KPMastery, type KPWeak, type MistakeSummaryItem } from '@/api/analytics'
import AppLayout from '@/components/AppLayout.vue'
import { DataAnalysis, Warning, ChatDotRound } from '@element-plus/icons-vue'

const loading = ref(true)
const masteryBySubject = ref<Record<string, KPMastery[]>>({})
const weakPoints = ref<KPWeak[]>([])
const mistakes = ref<MistakeSummaryItem[]>([])

onMounted(async () => {
  try {
    const [m, w, ms] = await Promise.all([
      analyticsApi.getUserMastery(),
      analyticsApi.getWeakPoints(10),
      analyticsApi.getMistakeSummary().catch(() => ({ data: [] as MistakeSummaryItem[] })),
    ])
    masteryBySubject.value = m.data
    weakPoints.value = w.data
    mistakes.value = ms.data
  } catch (e) {
    console.error(e)
  } finally {
    loading.value = false
  }
})

const overallStats = computed(() => {
  const all = Object.values(masteryBySubject.value).flat()
  if (!all.length) return { avg: 0, total: 0, mastered: 0, weak: 0 }
  const avg = all.reduce((s, k) => s + k.score, 0) / all.length
  const mastered = all.filter(k => k.score >= 0.8).length
  const weak = all.filter(k => k.score < 0.5).length
  return { avg: Math.round(avg * 100), total: all.length, mastered, weak }
})

const subjectStats = computed(() => {
  return Object.entries(masteryBySubject.value).map(([subject, kps]) => {
    const avg = kps.length ? kps.reduce((s, k) => s + k.score, 0) / kps.length : 0
    return { subject, count: kps.length, avg: Math.round(avg * 100) }
  })
})

function scoreColor(score: number) {
  if (score >= 0.8) return '#10b981'
  if (score >= 0.5) return '#f59e0b'
  return '#ef4444'
}

function scoreTag(score: number) {
  if (score >= 0.8) return '🟢'
  if (score >= 0.5) return '🟡'
  if (score > 0) return '🔴'
  return '⚪'
}
</script>

<template>
  <AppLayout>
    <div class="analytics">
      <el-skeleton :loading="loading" animated :count="6">
        <div class="overview">
          <el-card shadow="hover" class="overview-card">
            <div class="ov-label">总体掌握度</div>
            <div class="ov-val" :style="{ color: scoreColor(overallStats.avg / 100) }">
              {{ overallStats.avg }}%
            </div>
            <div class="ov-meta">覆盖 {{ overallStats.total }} 个知识点</div>
          </el-card>
          <el-card v-for="s in subjectStats" :key="s.subject" shadow="hover" class="overview-card">
            <div class="ov-label">{{ s.subject }}</div>
            <div class="ov-val" :style="{ color: scoreColor(s.avg / 100) }">{{ s.avg }}%</div>
            <div class="ov-meta">{{ s.count }} 个知识点</div>
          </el-card>
        </div>

        <div class="content-cols">
          <el-card shadow="hover">
            <template #header>
              <div class="card-hd">
                <span><el-icon><Warning /></el-icon> 薄弱知识点 Top {{ weakPoints.length }}</span>
              </div>
            </template>
            <el-empty v-if="!weakPoints.length" description="暂无薄弱数据，做几道题看看" :image-size="80" />
            <div v-for="wp in weakPoints" :key="wp.kp_id" class="weak-row">
              <div class="weak-info">
                <span class="weak-name">
                  <el-tag size="small">{{ wp.subject }}</el-tag>
                  {{ wp.name }}
                </span>
                <div class="weak-sub">
                  <span v-if="wp.chapter">{{ wp.chapter }} / {{ wp.section || '—' }}</span>
                  <span class="weak-err">错 {{ wp.error_count }} 次</span>
                </div>
                <div v-if="wp.top_mistakes.length" class="weak-mistakes">
                  <el-tag v-for="m in wp.top_mistakes" :key="m.name" size="small" type="danger" effect="plain">
                    {{ m.name }} ({{ m.times }})
                  </el-tag>
                </div>
              </div>
              <div class="weak-score" :style="{ color: scoreColor(wp.mastery_score ?? 0) }">
                {{ scoreTag(wp.mastery_score ?? 0) }}
                {{ wp.mastery_score !== null ? Math.round(wp.mastery_score * 100) + '%' : '—' }}
              </div>
            </div>
          </el-card>

          <el-card shadow="hover">
            <template #header>
              <div class="card-hd">
                <span><el-icon><ChatDotRound /></el-icon> 错因分布</span>
              </div>
            </template>
            <el-empty v-if="!mistakes.length" description="暂无错因数据" :image-size="80" />
            <div v-for="m in mistakes" :key="m.mistake_name" class="mistake-row">
              <span class="mistake-name">{{ m.mistake_name }}</span>
              <div class="mistake-bar">
                <div class="mistake-bar-fill" :style="{ width: Math.min(m.times * 10, 100) + '%' }" />
              </div>
              <span class="mistake-times">{{ m.times }} 次</span>
            </div>
          </el-card>
        </div>

        <el-card shadow="hover">
          <template #header>
            <div class="card-hd">
              <span><el-icon><DataAnalysis /></el-icon> 按学科掌握度</span>
            </div>
          </template>
          <el-empty v-if="!Object.keys(masteryBySubject).length" description="暂无数据" :image-size="80" />
          <div v-for="[subject, kps] in Object.entries(masteryBySubject)" :key="subject" class="subject-block">
            <div class="subject-title">
              <strong>{{ subject }}</strong>
              <span class="subject-count">{{ kps.length }} 个知识点</span>
            </div>
            <div class="kp-grid">
              <div v-for="kp in kps" :key="kp.kp_id" class="kp-cell" :title="`${kp.code} | ${kp.chapter || ''}/${kp.section || ''}`">
                <span class="kp-dot" :style="{ background: scoreColor(kp.score) }" />
                <span class="kp-name">{{ kp.name }}</span>
                <span class="kp-pct">{{ Math.round(kp.score * 100) }}%</span>
              </div>
            </div>
          </div>
        </el-card>
      </el-skeleton>
    </div>
  </AppLayout>
</template>

<style scoped>
.analytics { display: flex; flex-direction: column; gap: 20px; }
.overview { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; }
.overview-card { text-align: center; }
.overview-card :deep(.el-card__body) { padding: 20px; }
.ov-label { font-size: 13px; color: #6b7280; margin-bottom: 8px; }
.ov-val { font-size: 32px; font-weight: 800; line-height: 1.1; }
.ov-meta { font-size: 12px; color: #9ca3af; margin-top: 6px; }

.content-cols { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 900px) { .content-cols { grid-template-columns: 1fr; } }
.card-hd { display: flex; align-items: center; gap: 6px; font-weight: 600; }

.weak-row { display: flex; align-items: center; gap: 12px; padding: 12px 0; border-bottom: 1px solid #f3f4f6; }
.weak-row:last-child { border-bottom: none; }
.weak-info { flex: 1; min-width: 0; }
.weak-name { font-size: 14px; font-weight: 500; display: flex; align-items: center; gap: 8px; }
.weak-sub { font-size: 12px; color: #9ca3af; margin-top: 4px; display: flex; gap: 12px; }
.weak-err { color: #ef4444; }
.weak-mistakes { margin-top: 6px; display: flex; gap: 4px; flex-wrap: wrap; }
.weak-score { font-size: 16px; font-weight: 700; min-width: 60px; text-align: right; }

.mistake-row { display: flex; align-items: center; gap: 12px; padding: 8px 0; font-size: 13px; }
.mistake-name { width: 140px; flex-shrink: 0; }
.mistake-bar { flex: 1; height: 8px; background: #f3f4f6; border-radius: 4px; overflow: hidden; }
.mistake-bar-fill { height: 100%; background: linear-gradient(90deg, #f59e0b, #ef4444); border-radius: 4px; transition: width 0.3s; }
.mistake-times { font-size: 12px; color: #6b7280; min-width: 50px; text-align: right; }

.subject-block { margin-bottom: 18px; }
.subject-title { display: flex; align-items: baseline; gap: 10px; margin-bottom: 10px; }
.subject-count { font-size: 12px; color: #9ca3af; }
.kp-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px; }
.kp-cell { display: flex; align-items: center; gap: 6px; padding: 6px 10px; background: #f9fafb; border-radius: 6px; font-size: 13px; }
.kp-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.kp-name { flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.kp-pct { font-size: 11px; color: #6b7280; }
</style>
