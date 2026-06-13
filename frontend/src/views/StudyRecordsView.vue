<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { studyApi } from '@/api/study'
import type { StudyRecordResponse } from '@/types'
import AppLayout from '@/components/AppLayout.vue'

const records = ref<StudyRecordResponse[]>([])
const loading = ref(true)
const showForm = ref(false)
const saving = ref(false)

const subject = ref('')
const durationSeconds = ref(0)
const isCorrect = ref<string>('')
const emotionScore = ref<number | null>(null)

onMounted(async () => {
  try {
    const res = await studyApi.listRecords()
    records.value = res.data
  } catch {
    // silent
  } finally {
    loading.value = false
  }
})

async function handleCreate() {
  if (!subject.value || durationSeconds.value <= 0) return
  saving.value = true
  try {
    const payload: any = {
      subject: subject.value,
      duration_seconds: durationSeconds.value,
    }
    if (isCorrect.value !== '') {
      payload.is_correct = isCorrect.value === 'true'
    }
    if (emotionScore.value !== null) {
      payload.emotion_score = emotionScore.value
    }
    const res = await studyApi.createRecord(payload)
    records.value.unshift(res.data)
    showForm.value = false
    subject.value = ''
    durationSeconds.value = 0
    isCorrect.value = ''
    emotionScore.value = null
  } finally {
    saving.value = false
  }
}

function formatDuration(sec: number) {
  const h = Math.floor(sec / 3600)
  const m = Math.floor((sec % 3600) / 60)
  if (h > 0) return `${h}小时${m}分钟`
  return `${m}分钟`
}
</script>

<template>
  <AppLayout>
    <div class="records-page">
      <div class="page-toolbar">
        <span class="record-count">共 {{ records.length }} 条记录</span>
        <button class="btn-create" @click="showForm = !showForm">
          {{ showForm ? '取消' : '+ 记录学习' }}
        </button>
      </div>

      <div v-if="showForm" class="form-card">
        <h3 class="form-title">记录学习</h3>
        <form @submit.prevent="handleCreate">
          <div class="form-grid">
            <div class="field">
              <label>科目</label>
              <input v-model="subject" placeholder="例：高等数学" />
            </div>
            <div class="field">
              <label>学习时长（秒）</label>
              <input v-model.number="durationSeconds" type="number" min="1" placeholder="例：3600" />
            </div>
            <div class="field">
              <label>是否正确</label>
              <select v-model="isCorrect">
                <option value="">不指定</option>
                <option value="true">正确</option>
                <option value="false">错误</option>
              </select>
            </div>
            <div class="field">
              <label>情绪评分（0~1）</label>
              <input v-model.number="emotionScore" type="number" step="0.1" min="0" max="1" placeholder="例：0.8" />
            </div>
          </div>
          <div class="form-actions">
            <button type="submit" class="btn-primary" :disabled="saving">
              {{ saving ? '保存中...' : '保存记录' }}
            </button>
          </div>
        </form>
      </div>

      <div v-if="loading" class="loading-state">加载中...</div>

      <div v-else-if="records.length === 0" class="empty-state">
        <div class="empty-icon">📝</div>
        <p>还没有学习记录</p>
        <button class="btn-create" @click="showForm = true">记录第一次学习</button>
      </div>

      <div v-else class="record-table">
        <div class="table-header">
          <span class="col-subject">科目</span>
          <span class="col-result">结果</span>
          <span class="col-duration">时长</span>
          <span class="col-emotion">情绪</span>
          <span class="col-date">日期</span>
        </div>
        <div v-for="r in records" :key="r.id" class="table-row">
          <span class="col-subject"><span class="tag-subject">{{ r.subject }}</span></span>
          <span class="col-result">
            <span :class="['tag-result', r.is_correct === null ? '' : r.is_correct ? 'correct' : 'wrong']">
              {{ r.is_correct === null ? '待批改' : r.is_correct ? '正确' : '错误' }}
            </span>
          </span>
          <span class="col-duration">{{ formatDuration(r.duration_seconds) }}</span>
          <span class="col-emotion">{{ r.emotion_score !== null ? r.emotion_score : '-' }}</span>
          <span class="col-date">{{ r.created_at?.slice(0, 10) }}</span>
        </div>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
.records-page { max-width: 960px; }
.page-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}
.record-count { font-size: 14px; color: #6b7280; }
.btn-create {
  padding: 9px 20px;
  background: #4f46e5;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  cursor: pointer;
}
.btn-create:hover { background: #4338ca; }
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
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  margin-bottom: 8px;
}
.field label {
  display: block;
  font-size: 13px;
  font-weight: 500;
  color: #374151;
  margin-bottom: 4px;
}
.field input, .field select {
  width: 100%;
  padding: 9px 12px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 15px;
  outline: none;
  box-sizing: border-box;
}
.field input:focus, .field select:focus { border-color: #4f46e5; }
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
.record-table {
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
  overflow: hidden;
}
.table-header {
  display: grid;
  grid-template-columns: 1fr 100px 120px 80px 110px;
  gap: 12px;
  padding: 12px 20px;
  background: #f9fafb;
  font-size: 13px;
  font-weight: 600;
  color: #6b7280;
  border-bottom: 1px solid #e5e7eb;
}
.table-row {
  display: grid;
  grid-template-columns: 1fr 100px 120px 80px 110px;
  gap: 12px;
  padding: 14px 20px;
  font-size: 14px;
  align-items: center;
  border-bottom: 1px solid #f3f4f6;
  transition: background 0.1s;
}
.table-row:last-child { border-bottom: none; }
.table-row:hover { background: #f9fafb; }
.tag-subject {
  background: #eef2ff;
  color: #4f46e5;
  padding: 3px 10px;
  border-radius: 10px;
  font-size: 13px;
  font-weight: 500;
}
.tag-result.correct { color: #16a34a; font-weight: 500; }
.tag-result.wrong { color: #dc2626; font-weight: 500; }
.col-duration { color: #374151; }
.col-emotion { color: #6b7280; }
.col-date { color: #9ca3af; font-size: 13px; }
.loading-state { text-align: center; color: #9ca3af; padding: 60px 0; }
.empty-state { text-align: center; padding: 60px 0; color: #6b7280; }
.empty-icon { font-size: 48px; margin-bottom: 12px; }
.empty-state p { margin-bottom: 16px; }
</style>
