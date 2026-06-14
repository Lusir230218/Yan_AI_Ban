<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import AppLayout from '@/components/AppLayout.vue'
import { questionApi } from '@/api/questions'
import type { QuestionResponse, AnswerResult } from '@/types'
import { renderMath } from '@/utils/math'

const questions = ref<QuestionResponse[]>([])
const loading = ref(true)
const selectedId = ref<number | null>(null)
const selectedAnswers = ref<string[]>([])
const submitting = ref(false)
const result = ref<AnswerResult | null>(null)
const subjectFilter = ref<string>('')
const startTime = ref(0)

const subjects = ['', '数学', '英语', '政治']

const current = computed(() =>
  questions.value.find(q => q.id === selectedId.value)
)

const optionsList = computed(() => {
  if (!current.value) return []
  try {
    return JSON.parse(current.value.options) as string[]
  } catch {
    return []
  }
})

const isMulti = computed(() => current.value?.question_type === 'multi_choice')

onMounted(async () => {
  try {
    const res = await questionApi.listQuestions()
    questions.value = res.data
  } finally {
    loading.value = false
  }
})

async function selectQuestion(id: number) {
  selectedId.value = id
  selectedAnswers.value = []
  result.value = null
  startTime.value = Date.now()
}

async function toggleAnswer(opt: string) {
  const letter = opt.charAt(0)
  if (isMulti.value) {
    const idx = selectedAnswers.value.indexOf(letter)
    if (idx >= 0) selectedAnswers.value.splice(idx, 1)
    else selectedAnswers.value.push(letter)
  } else {
    selectedAnswers.value = [letter]
  }
}

function isSelected(opt: string) {
  return selectedAnswers.value.includes(opt.charAt(0))
}

function stemPreview(stem: string) {
  return stem.replace(/\\?\$.*?\$\$?/g, '').slice(0, 30)
}

async function handleSubmit() {
  if (!current.value || selectedAnswers.value.length === 0) return
  submitting.value = true
  try {
    const duration = Math.floor((Date.now() - startTime.value) / 1000)
    const res = await questionApi.submitAnswer(current.value.id, {
      answer: selectedAnswers.value.sort().join(''),
      duration_seconds: duration,
      subject: current.value.subject,
    })
    result.value = res.data
  } finally {
    submitting.value = false
  }
}

async function filterBySubject() {
  loading.value = true
  try {
    const res = await questionApi.listQuestions(
      subjectFilter.value ? { subject: subjectFilter.value } : undefined
    )
    questions.value = res.data
    selectedId.value = null
    result.value = null
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <AppLayout>
    <div class="practice-layout">
      <!-- 左侧题目列表 -->
      <aside class="question-list-panel">
        <div class="panel-header">
          <h3>题目列表</h3>
          <select v-model="subjectFilter" class="subject-select" @change="filterBySubject">
            <option value="">全部科目</option>
            <option v-for="s in subjects.filter(Boolean)" :key="s" :value="s">{{ s }}</option>
          </select>
        </div>
        <div v-if="loading" class="loading">加载中...</div>
        <div v-else class="list-items">
          <button
            v-for="q in questions"
            :key="q.id"
            :class="['list-item', { active: q.id === selectedId }]"
            @click="selectQuestion(q.id)"
          >
            <span class="item-type">{{ { single_choice: '单选', multi_choice: '多选', true_false: '判断' }[q.question_type] }}</span>
            <span class="item-stem">{{ stemPreview(q.stem) }}...</span>
          </button>
          <div v-if="questions.length === 0" class="empty">暂无题目</div>
        </div>
      </aside>

      <!-- 右侧答题区 -->
      <div class="question-area">
        <div v-if="!current" class="placeholder">请从左侧选择一道题目开始练习</div>
        <template v-else>
          <div class="question-card">
            <div class="q-meta">
              <span class="q-subject">{{ current.subject }}</span>
              <span class="q-type">{{ { single_choice: '单选题', multi_choice: '多选题', true_false: '判断题' }[current.question_type] }}</span>
              <span class="q-difficulty">{{ '⭐'.repeat(current.difficulty) }}</span>
            </div>
            <div class="q-stem" v-html="renderMath(current.stem)"></div>
            <div class="q-options">
              <button
                v-for="opt in optionsList"
                :key="opt"
                :class="['option-btn', { selected: isSelected(opt) }]"
                @click="toggleAnswer(opt)"
                :disabled="!!result"
                v-html="renderMath(opt)"
              ></button>
            </div>
            <button
              v-if="!result"
              class="submit-btn"
              :disabled="selectedAnswers.length === 0 || submitting"
              @click="handleSubmit"
            >
              {{ submitting ? '提交中...' : '提交答案' }}
            </button>
          </div>

          <!-- 反馈 -->
          <div v-if="result" :class="['feedback', result.is_correct ? 'correct' : 'wrong']">
            <div class="feedback-icon">{{ result.is_correct ? '✅' : '❌' }}</div>
            <div class="feedback-detail">
              <p class="feedback-title">{{ result.is_correct ? '回答正确！' : '回答错误' }}</p>
              <p v-if="!result.is_correct" class="correct-answer">
                正确答案：<strong>{{ result.correct_answer }}</strong>
              </p>
              <p v-if="result.explanation" class="explanation" v-html="renderMath(result.explanation)"></p>
            </div>
            <button class="next-btn" @click="result = null; selectedAnswers = []">继续</button>
          </div>
        </template>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
.practice-layout {
  display: flex;
  gap: 20px;
  height: calc(100vh - 100px);
}

.question-list-panel {
  width: 280px;
  min-width: 280px;
  background: #fff;
  border-radius: 12px;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.panel-header {
  padding: 16px;
  border-bottom: 1px solid #e5e7eb;
}
.panel-header h3 {
  margin: 0 0 10px;
  font-size: 16px;
  color: #1f2937;
}
.subject-select {
  width: 100%;
  padding: 8px;
  border: 1px solid #d1d5db;
  border-radius: 6px;
  font-size: 13px;
  background: #fff;
}

.list-items {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.list-item {
  display: block;
  width: 100%;
  text-align: left;
  padding: 10px 12px;
  border: none;
  background: transparent;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 4px;
  font-size: 13px;
}
.list-item:hover { background: #f3f4f6; }
.list-item.active { background: #eef2ff; }
.item-type {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
  background: #e5e7eb;
  color: #6b7280;
  margin-right: 6px;
}
.item-stem { color: #374151; }

.question-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #9ca3af;
  font-size: 16px;
  background: #fff;
  border-radius: 12px;
}

.question-card {
  background: #fff;
  border-radius: 12px;
  padding: 28px;
}

.q-meta {
  display: flex;
  gap: 10px;
  margin-bottom: 16px;
}
.q-subject, .q-type {
  padding: 3px 10px;
  border-radius: 6px;
  font-size: 13px;
  background: #eef2ff;
  color: #4f46e5;
}
.q-difficulty { font-size: 14px; color: #f59e0b; }

.q-stem {
  font-size: 16px;
  line-height: 1.7;
  color: #1f2937;
  margin-bottom: 24px;
  white-space: pre-wrap;
}

.q-options {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-bottom: 20px;
}
.option-btn {
  text-align: left;
  padding: 14px 18px;
  border: 2px solid #e5e7eb;
  background: #fff;
  border-radius: 10px;
  font-size: 15px;
  cursor: pointer;
  transition: all 0.15s;
  color: #374151;
}
.option-btn:hover { border-color: #a5b4fc; background: #fafaff; }
.option-btn.selected {
  border-color: #4f46e5;
  background: #eef2ff;
  font-weight: 500;
}
.option-btn:disabled { cursor: default; opacity: 0.7; }

.submit-btn {
  padding: 12px 32px;
  background: #4f46e5;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
}
.submit-btn:hover { background: #4338ca; }
.submit-btn:disabled { background: #a5b4fc; cursor: not-allowed; }

.feedback {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  display: flex;
  gap: 16px;
  align-items: flex-start;
}
.feedback.correct { border: 2px solid #10b981; }
.feedback.wrong { border: 2px solid #ef4444; }
.feedback-icon { font-size: 28px; }
.feedback-detail { flex: 1; }
.feedback-title { font-size: 17px; font-weight: 600; margin: 0 0 8px; }
.correct-answer { font-size: 14px; color: #374151; margin: 0 0 4px; }
.explanation {
  font-size: 14px;
  color: #6b7280;
  line-height: 1.6;
  margin: 0;
  background: #f9fafb;
  padding: 12px;
  border-radius: 8px;
}
.next-btn {
  padding: 8px 20px;
  border: 1px solid #d1d5db;
  background: #fff;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  white-space: nowrap;
}
.next-btn:hover { background: #f9fafb; }

.loading, .empty {
  padding: 32px;
  text-align: center;
  color: #9ca3af;
}
</style>
