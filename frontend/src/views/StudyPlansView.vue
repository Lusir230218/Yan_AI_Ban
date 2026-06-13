<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { studyApi } from '@/api/study'
import type { StudyPlanResponse } from '@/types'
import AppLayout from '@/components/AppLayout.vue'

const plans = ref<StudyPlanResponse[]>([])
const loading = ref(true)
const generating = ref(false)
const showForm = ref(false)
const saving = ref(false)

const phase = ref('')
const focus = ref('')
const startDate = ref('')
const endDate = ref('')
const dailyTasks = ref('')

onMounted(async () => {
  try {
    const res = await studyApi.listPlans()
    plans.value = res.data
  } catch {
    // silent
  } finally {
    loading.value = false
  }
})

async function handleGenerate() {
  generating.value = true
  try {
    const res = await studyApi.generatePlans()
    plans.value = res.data
  } finally {
    generating.value = false
  }
}

async function handleCreate() {
  if (!phase.value || !startDate.value || !endDate.value) return
  saving.value = true
  try {
    const res = await studyApi.createPlan({
      phase: phase.value,
      focus: focus.value || null,
      start_date: startDate.value,
      end_date: endDate.value,
      daily_tasks: dailyTasks.value || null,
    })
    plans.value.unshift(res.data)
    showForm.value = false
    phase.value = ''
    focus.value = ''
    startDate.value = ''
    endDate.value = ''
    dailyTasks.value = ''
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <AppLayout>
    <div class="plans-page">
      <div class="page-toolbar">
        <span class="plan-count">共 {{ plans.length }} 个计划</span>
        <div class="toolbar-actions">
          <button class="btn-generate" :disabled="generating" @click="handleGenerate">
            {{ generating ? '生成中...' : '🤖 AI 生成计划' }}
          </button>
          <button class="btn-create" @click="showForm = !showForm">
            {{ showForm ? '取消' : '+ 新建计划' }}
          </button>
        </div>
      </div>

      <div v-if="showForm" class="form-card">
        <h3 class="form-title">新建学习计划</h3>
        <form @submit.prevent="handleCreate">
          <div class="form-grid">
            <div class="field">
              <label>阶段名称</label>
              <input v-model="phase" placeholder="例：基础阶段" />
            </div>
            <div class="field">
              <label>开始日期</label>
              <input v-model="startDate" type="date" />
            </div>
            <div class="field">
              <label>结束日期</label>
              <input v-model="endDate" type="date" />
            </div>
            <div class="field">
              <label>学习重点</label>
              <input v-model="focus" placeholder="例：高等数学基础概念" />
            </div>
          </div>
          <div class="field">
            <label>每日任务描述</label>
            <textarea v-model="dailyTasks" placeholder="描述每天需要完成的任务" rows="3"></textarea>
          </div>
          <div class="form-actions">
            <button type="submit" class="btn-primary" :disabled="saving">
              {{ saving ? '创建中...' : '创建计划' }}
            </button>
          </div>
        </form>
      </div>

      <div v-if="loading" class="loading-state">加载中...</div>

      <div v-else-if="plans.length === 0" class="empty-state">
        <div class="empty-icon">📋</div>
        <p>还没有学习计划</p>
        <button class="btn-create" @click="showForm = true">创建第一个计划</button>
      </div>

      <div v-else class="plan-list">
        <div v-for="p in plans" :key="p.id" class="plan-card">
          <div class="plan-top">
            <div class="plan-left">
              <h4 class="plan-phase">{{ p.phase }}</h4>
              <span v-if="p.focus" class="plan-focus">{{ p.focus }}</span>
              <span class="plan-date">{{ p.start_date }} ~ {{ p.end_date }}</span>
            </div>
            <span :class="['plan-status', p.status]">
              {{ p.status === 'active' ? '进行中' : '已完成' }}
            </span>
          </div>
          <div v-if="p.daily_tasks" class="plan-tasks">{{ p.daily_tasks }}</div>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
.plans-page { max-width: 800px; }
.page-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.plan-count { font-size: 14px; color: #6b7280; }
.toolbar-actions { display: flex; gap: 10px; }
.btn-create, .btn-generate {
  padding: 9px 20px;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
}
.btn-create {
  background: #4f46e5;
  color: #fff;
}
.btn-create:hover { background: #4338ca; }
.btn-generate {
  background: #059669;
  color: #fff;
}
.btn-generate:hover { background: #047857; }
.btn-generate:disabled { background: #6ee7b7; cursor: not-allowed; }
.form-card {
  background: #fff;
  border-radius: 10px;
  padding: 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
  margin-bottom: 20px;
}
.form-title {
  font-size: 16px;
  font-weight: 600;
  margin: 0 0 20px;
  padding-bottom: 12px;
  border-bottom: 1px solid #f3f4f6;
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}
.field label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: #374151;
  margin-bottom: 4px;
}
.field input, .field textarea {
  width: 100%;
  padding: 9px 12px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 15px;
  outline: none;
  box-sizing: border-box;
}
.field input:focus, .field textarea:focus { border-color: #4f46e5; }
.form-actions {
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #f3f4f6;
}
.btn-primary {
  padding: 9px 24px;
  background: #4f46e5;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
}
.btn-primary:disabled { background: #a5b4fc; }
.plan-list { display: flex; flex-direction: column; gap: 12px; }
.plan-card {
  background: #fff;
  border-radius: 10px;
  padding: 20px 24px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}
.plan-top { display: flex; justify-content: space-between; align-items: flex-start; }
.plan-left { display: flex; flex-direction: column; gap: 4px; }
.plan-phase { font-size: 16px; font-weight: 600; margin: 0; }
.plan-focus { font-size: 13px; color: #059669; font-weight: 500; }
.plan-date { font-size: 13px; color: #6b7280; }
.plan-status {
  font-size: 12px; padding: 4px 12px; border-radius: 10px; font-weight: 500; flex-shrink: 0;
}
.plan-status.active { background: #dcfce7; color: #16a34a; }
.plan-status.completed { background: #f3f4f6; color: #6b7280; }
.plan-tasks {
  margin-top: 12px; padding-top: 12px; border-top: 1px solid #f3f4f6;
  font-size: 14px; color: #374151; line-height: 1.6; white-space: pre-wrap;
}
.loading-state { text-align: center; color: #9ca3af; padding: 60px 0; }
.empty-state { text-align: center; padding: 60px 0; color: #6b7280; }
.empty-icon { font-size: 48px; margin-bottom: 12px; }
.empty-state p { margin-bottom: 16px; font-size: 15px; }
</style>
