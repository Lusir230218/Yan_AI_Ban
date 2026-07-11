<script setup lang="ts">
import { ref, computed } from 'vue'
import { Upload, Lightning, Reading, Edit, Delete } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import AppLayout from '@/components/AppLayout.vue'
import { aiSolve } from '@/api/ai'
import type { AiSolveResponse } from '@/types'

const text = ref('')
const imageFile = ref<File | null>(null)
const imagePreview = ref<string | null>(null)
const multiModal = ref(false)
const loading = ref(false)
const result = ref<AiSolveResponse | null>(null)
const step = ref<'input' | 'processing' | 'result'>('input')

const hasInput = computed(() => text.value.trim() || imageFile.value)

function handleImageUpload(file: File) {
  const maxSize = 10 * 1024 * 1024
  if (file.size > maxSize) {
    ElMessage.warning('图片最大 10MB')
    return
  }
  imageFile.value = file
  const reader = new FileReader()
  reader.onload = (e) => { imagePreview.value = e.target?.result as string }
  reader.readAsDataURL(file)
}

function clearImage() {
  imageFile.value = null
  imagePreview.value = null
}

async function handleSubmit() {
  if (!hasInput.value) return

  loading.value = true
  step.value = 'processing'
  result.value = null

  try {
    const res = await aiSolve({
      image: imageFile.value || undefined,
      text: text.value.trim() || undefined,
      multi_modal: multiModal.value,
    })
    if (res.error) {
      ElMessage.error(res.error)
      step.value = 'input'
    } else {
      result.value = res
      step.value = 'result'
    }
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || '请求失败')
    step.value = 'input'
  } finally {
    loading.value = false
  }
}

function reset() {
  text.value = ''
  clearImage()
  result.value = null
  step.value = 'input'
}

const modeLabel = computed(() =>
  multiModal.value ? 'GPT-4o Vision（公式精准）' : 'OCR 模式（通用）'
)
</script>

<template>
  <AppLayout>
    <div class="ai-solve-page">
      <h2 class="page-title">AI 解答</h2>

      <!-- Input -->
      <div v-if="step === 'input'" class="input-section">
      <!-- Text input -->
      <el-input
        v-model="text"
        type="textarea"
        :rows="6"
        placeholder="在此粘贴题目文本...（或在下方的上传区上传图片）"
        class="text-input"
      />

      <!-- Upload area -->
      <div class="upload-area">
        <div v-if="!imagePreview" class="upload-dropzone" @dragover.prevent @drop.prevent="handleImageUpload(($event.dataTransfer?.files[0]) as File)">
          <el-upload
            :show-file-list="false"
            :before-upload="(f: File) => { handleImageUpload(f); return false }"
            accept="image/jpeg,image/png"
          >
            <el-icon :size="36" color="#a78bfa"><Upload /></el-icon>
            <p class="upload-text">点击上传或拖拽图片到此</p>
            <p class="upload-hint">支持 JPG / PNG，最大 10MB</p>
          </el-upload>
        </div>
        <div v-else class="image-preview">
          <img :src="imagePreview" alt="preview" />
          <el-button :icon="Delete" circle size="small" class="clear-btn" @click="clearImage" />
        </div>
      </div>

      <!-- Options -->
      <div class="options-row">
        <el-switch v-model="multiModal" active-text="多模态模式" />
        <span class="mode-hint">{{ modeLabel }}</span>
      </div>

      <!-- Submit -->
      <el-button
        type="primary"
        size="large"
        :icon="Lightning"
        :disabled="!hasInput"
        :loading="loading"
        class="submit-btn"
        @click="handleSubmit"
      >
        {{ imageFile ? '识别并解答' : '开始解答' }}
      </el-button>
    </div>

    <!-- Processing -->
    <div v-if="step === 'processing'" class="processing-section">
      <el-skeleton :loading="true" animated :count="3">
        <div class="processing-status">
          <el-icon :size="32" class="spin"><Lightning /></el-icon>
          <p>{{ multiModal ? 'GPT-4o Vision 分析中...' : 'OCR 识别中...' }}</p>
        </div>
      </el-skeleton>
    </div>

    <!-- Result -->
    <div v-if="step === 'result' && result" class="result-section">
      <el-card shadow="hover" class="result-card">
        <template #header>
          <div class="result-header">
            <span class="result-title">解答结果</span>
            <el-button :icon="Edit" text size="small" @click="reset">重新输入</el-button>
          </div>
        </template>

        <!-- Question info -->
        <div class="question-meta">
          <el-tag size="small" type="info">{{ result.question?.subject }}</el-tag>
          <el-tag v-if="result.question?.exam_variant" size="small">{{ result.question?.exam_variant }}</el-tag>
          <el-tag size="small" :type="result.question?.question_type === 'choice' ? 'success' : 'warning'">
            {{ { choice: '选择题', multi_choice: '多选题', fill_blank: '填空题', essay: '解答题', true_false: '判断题', material_analysis: '材料题' }[result.question?.question_type || ''] || result.question?.question_type }}
          </el-tag>
          <el-tag size="small">难度 {{ result.question?.difficulty }}</el-tag>
        </div>

        <div class="q-stem" v-html="result.question?.stem" />

        <!-- Options -->
        <div v-if="result.question?.options && result.question.options !== '[]'" class="q-options">
          <p v-for="opt in JSON.parse(result.question.options)" :key="opt" class="option-item">
            {{ opt }}
          </p>
        </div>

        <!-- Grading result -->
        <div v-if="result.is_correct !== null" class="grade-result" :class="result.is_correct ? 'correct' : 'wrong'">
          <div class="grade-icon">{{ result.is_correct ? '✓' : '✗' }}</div>
          <div class="grade-text">
            <p class="grade-title">{{ result.is_correct ? '回答正确' : '回答错误' }}</p>
            <p v-if="result.user_answer">你的答案：{{ result.user_answer }}</p>
            <p>正确答案：{{ result.correct_answer }}</p>
          </div>
        </div>

        <!-- Correct answer (solve mode) -->
        <div v-else-if="result.correct_answer" class="answer-box">
          <p class="answer-label">正确答案：<strong>{{ result.correct_answer }}</strong></p>
        </div>

        <!-- Error analysis -->
        <div v-if="result.errors?.length" class="errors-section">
          <h4>错题分析</h4>
          <ul>
            <li v-for="(err, i) in result.errors" :key="i">{{ err }}</li>
          </ul>
        </div>

        <!-- Explanation -->
        <div v-if="result.explanation" class="explanation-section">
          <h4>详细解析</h4>
          <p class="explanation-text">{{ result.explanation }}</p>
        </div>
      </el-card>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
.ai-solve-page {
  max-width: 800px;
  margin: 0 auto;
}
.page-title {
  font-size: 22px;
  font-weight: 700;
  margin: 0 0 24px;
  color: #1f2937;
}

/* Input */
.input-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.text-input :deep(.el-textarea__inner) {
  min-height: 120px;
  font-size: 15px;
  line-height: 1.7;
}
.upload-area { width: 100%; }
.upload-dropzone {
  border: 2px dashed #d1d5db;
  border-radius: 12px;
  padding: 32px;
  text-align: center;
  transition: all 0.2s;
  cursor: pointer;
}
.upload-dropzone:hover {
  border-color: #a78bfa;
  background: #f5f3ff;
}
.upload-text { color: #6b7280; margin: 8px 0 4px; font-size: 14px; }
.upload-hint { color: #9ca3af; margin: 0; font-size: 12px; }
.image-preview {
  position: relative;
  border-radius: 12px;
  overflow: hidden;
}
.image-preview img {
  max-width: 100%;
  max-height: 300px;
  display: block;
  border-radius: 12px;
}
.clear-btn {
  position: absolute;
  top: 8px;
  right: 8px;
}
.options-row {
  display: flex;
  align-items: center;
  gap: 10px;
}
.mode-hint {
  font-size: 12px;
  color: #9ca3af;
}
.submit-btn {
  width: 100%;
  font-size: 16px;
}

/* Processing */
.processing-section {
  padding: 60px 0;
  text-align: center;
}
.processing-status {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  color: #6b7280;
}
.spin { animation: spin 1.5s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* Result */
.result-section { margin-top: 8px; }
.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.result-title { font-weight: 700; font-size: 16px; }
.question-meta {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}
.q-stem {
  font-size: 16px;
  line-height: 1.8;
  margin-bottom: 12px;
  color: #1f2937;
}
.q-options { margin-bottom: 16px; }
.option-item {
  padding: 8px 12px;
  margin: 4px 0;
  background: #f9fafb;
  border-radius: 6px;
  font-size: 14px;
}
.grade-result {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 16px;
  border-radius: 10px;
  margin-bottom: 16px;
}
.grade-result.correct {
  background: #ecfdf5;
  border: 1px solid #a7f3d0;
}
.grade-result.wrong {
  background: #fef2f2;
  border: 1px solid #fecaca;
}
.grade-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 800;
}
.correct .grade-icon { background: #10b981; color: #fff; }
.wrong .grade-icon { background: #ef4444; color: #fff; }
.grade-text p { margin: 2px 0; font-size: 14px; }
.grade-title { font-weight: 700; font-size: 16px !important; }
.answer-box {
  padding: 12px 16px;
  background: #f0fdf4;
  border-radius: 8px;
  margin-bottom: 16px;
}
.answer-label { font-size: 15px; margin: 0; }
.errors-section {
  margin-bottom: 16px;
}
.errors-section h4,
.explanation-section h4 {
  font-size: 15px;
  font-weight: 700;
  color: #1f2937;
  margin: 0 0 8px;
}
.errors-section ul {
  margin: 0;
  padding-left: 20px;
}
.errors-section li {
  color: #dc2626;
  font-size: 14px;
  margin: 4px 0;
}
.explanation-text {
  font-size: 14px;
  line-height: 1.8;
  color: #374151;
  white-space: pre-wrap;
}
</style>