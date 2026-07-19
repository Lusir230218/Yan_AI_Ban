<script setup lang="ts">
import { ref, nextTick } from 'vue'
import { Upload, Delete, Promotion, View, Clock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import AppLayout from '@/components/AppLayout.vue'
import { tutorApi } from '@/api/tutor'
import { renderMath } from '@/utils/math'
import type { TutorMessage, TutorSessionListItem } from '@/types'

const text = ref('')
const imageFile = ref<File | null>(null)
const imagePreview = ref<string | null>(null)
const loading = ref(false)
const sessionId = ref<number | null>(null)
const currentRound = ref(0)
const hintLevel = ref(1)
const sessionStatus = ref<string>('')
const messages = ref<TutorMessage[]>([])
const userInput = ref('')
const sending = ref(false)
const showAnswer = ref(false)
const answerContent = ref('')
const multiModal = ref(false)
const chatContainer = ref<HTMLElement | null>(null)

const historyVisible = ref(false)
const historyList = ref<TutorSessionListItem[]>([])
const historyLoading = ref(false)

const mathCache = new Map<string, string>()
function renderedHtml(text: string): string {
  if (!text) return ''
  const hit = mathCache.get(text)
  if (hit !== undefined) return hit
  const html = renderMath(text)
  mathCache.set(text, html)
  return html
}

const hasInput = () => text.value.trim() || imageFile.value
const canReveal = () => currentRound.value >= 2 && sessionStatus.value === 'active'

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

async function scrollToBottom() {
  await nextTick()
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

async function handleStart() {
  if (!hasInput()) return
  loading.value = true
  try {
    const res = await tutorApi.start({
      image: imageFile.value || undefined,
      text: text.value.trim() || undefined,
      multi_modal: multiModal.value,
    })
    if (res.error) {
      ElMessage.error(res.error)
      return
    }
    sessionId.value = res.session_id
    currentRound.value = res.current_round
    hintLevel.value = res.hint_level
    sessionStatus.value = res.status
    messages.value = [{
      role: 'assistant', content: res.message,
      round: res.current_round, hint_level: res.hint_level,
    }]
    await scrollToBottom()
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || '请求失败')
  } finally {
    loading.value = false
  }
}

async function handleSend() {
  const input = userInput.value.trim()
  if (!input || !sessionId.value || sending.value) return

  sending.value = true
  messages.value.push({
    role: 'user', content: input,
    round: currentRound.value, hint_level: hintLevel.value,
  })
  userInput.value = ''
  await scrollToBottom()

  try {
    const res = await tutorApi.continue_(sessionId.value, input)
    console.log('tutor continue response:', res)
    if (res.error) {
      ElMessage.error(res.error)
      return
    }
    currentRound.value = res.current_round
    hintLevel.value = res.hint_level
    sessionStatus.value = res.status
    messages.value.push({
      role: 'assistant', content: res.message,
      round: res.current_round, hint_level: res.hint_level,
    })
    await scrollToBottom()
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || '请求失败')
  } finally {
    sending.value = false
  }
}

async function handleReveal() {
  if (!sessionId.value) return
  sending.value = true
  try {
    const res = await tutorApi.reveal(sessionId.value)
    if (res.error) {
      ElMessage.error(res.error)
      return
    }
    showAnswer.value = true
    answerContent.value = res.message
    sessionStatus.value = 'completed'
    messages.value.push({
      role: 'assistant', content: res.message,
      round: currentRound.value, hint_level: 4,
    })
    await scrollToBottom()
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || '请求失败')
  } finally {
    sending.value = false
  }
}

async function openHistory() {
  historyVisible.value = true
  historyLoading.value = true
  try {
    historyList.value = await tutorApi.list()
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || '加载历史失败')
  } finally {
    historyLoading.value = false
  }
}

async function loadSession(id: number) {
  try {
    const res = await tutorApi.getSession(id)
    sessionId.value = res.id
    currentRound.value = res.current_round
    hintLevel.value = res.hint_level
    sessionStatus.value = res.status
    messages.value = (res.messages || []).map((m) => ({
      role: m.role,
      content: m.content,
      round: m.round,
      hint_level: m.hint_level,
    }))
    clearImage()
    text.value = res.question_snapshot?.stem || ''
    showAnswer.value = false
    answerContent.value = ''
    historyVisible.value = false
    await scrollToBottom()
  } catch (err: any) {
    ElMessage.error(err.response?.data?.detail || '加载会话失败')
  }
}

function formatTime(iso: string) {
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`
}

function handleReset() {
  text.value = ''
  clearImage()
  sessionId.value = null
  currentRound.value = 0
  hintLevel.value = 1
  sessionStatus.value = ''
  messages.value = []
  userInput.value = ''
  showAnswer.value = false
  answerContent.value = ''
}

const hintLabels: Record<number, string> = {
  1: '审题引导',
  2: '思路引导',
  3: '计算引导',
  4: '完整解析',
}
</script>

<template>
  <AppLayout>
    <div class="tutoring-page">
      <div class="page-header">
        <h2 class="page-title">AI 辅导</h2>
        <el-button :icon="Clock" @click="openHistory">历史会话</el-button>
      </div>

      <div v-if="!sessionId" class="input-section">
        <el-input
          v-model="text"
          type="textarea"
          :rows="5"
          placeholder="在此粘贴题目文本..."
        />
        <div class="upload-area">
          <div v-if="!imagePreview" class="upload-dropzone"
               @dragover.prevent @drop.prevent="handleImageUpload(($event.dataTransfer?.files![0]) as File)">
            <el-upload
              :show-file-list="false"
              :before-upload="(f: File) => { handleImageUpload(f); return false }"
              accept="image/jpeg,image/png"
            >
              <el-icon :size="32" color="#a78bfa"><Upload /></el-icon>
              <p class="upload-text">点击上传题目图片</p>
              <p class="upload-hint">支持 JPG / PNG，最大 10MB</p>
            </el-upload>
          </div>
          <div v-else class="image-preview">
            <img :src="imagePreview" alt="preview" />
            <el-button :icon="Delete" circle size="small" class="clear-btn" @click="clearImage" />
          </div>
        </div>
        <div class="options-row">
          <el-switch v-model="multiModal" active-text="多模态模式（GPT-4o Vision）" />
          <span class="mode-hint">{{ multiModal ? '直接识别图片，无需 OCR' : 'PaddleOCR 文字识别' }}</span>
        </div>
        <el-button
          type="primary" size="large" :icon="Promotion"
          :disabled="!hasInput()" :loading="loading"
          class="submit-btn" @click="handleStart"
        >
          开始 AI 辅导
        </el-button>
      </div>

      <div v-else class="tutor-session">
        <div class="session-header">
          <el-tag :type="sessionStatus === 'completed' ? 'success' : 'warning'" size="small">
            {{ sessionStatus === 'completed' ? '已完成' : '进行中' }}
          </el-tag>
          <span class="session-round">第 {{ currentRound + 1 }} 轮 · {{ hintLabels[hintLevel] || '' }}</span>
          <el-button text size="small" @click="handleReset">换一题</el-button>
        </div>

        <div class="split-layout">
          <div class="left-panel">
            <div v-if="imagePreview" class="question-image">
              <img :src="imagePreview" alt="题目图片" />
            </div>
            <div v-if="text" class="question-text">
              <h4>题目</h4>
              <p v-html="renderedHtml(text)" />
            </div>
          </div>

          <div class="right-panel">
            <div ref="chatContainer" class="chat-messages">
              <div v-for="(msg, i) in messages" :key="i"
                   :class="['chat-bubble', msg.role === 'assistant' ? 'ai' : 'user']">
                <div class="bubble-avatar">
                  {{ msg.role === 'assistant' ? 'AI' : '我' }}
                </div>
                <div class="bubble-content">
                  <p v-html="renderedHtml(msg.content)" />
                </div>
              </div>

              <div v-if="sending" class="chat-bubble ai">
                <div class="bubble-avatar">AI</div>
                <div class="bubble-content typing">思考中...</div>
              </div>
            </div>

            <div v-if="sessionStatus !== 'completed'" class="chat-input-area">
              <el-input
                v-model="userInput"
                type="textarea"
                :rows="2"
                placeholder="输入你的思考..."
                :disabled="sending"
                @keydown.enter.exact.prevent="handleSend"
              />
              <div class="chat-actions">
                <el-button
                  v-if="canReveal()"
                  :icon="View"
                  :disabled="sending"
                  @click="handleReveal"
                >
                  我看答案
                </el-button>
                <el-button
                  type="primary"
                  :icon="Promotion"
                  :disabled="!userInput.trim() || sending"
                  :loading="sending"
                  @click="handleSend"
                >
                  发送
                </el-button>
              </div>
            </div>

            <div v-if="sessionStatus === 'completed' && showAnswer" class="answer-reveal">
              <el-alert title="完整解析" type="success" :closable="false" show-icon>
                <p v-html="renderedHtml(answerContent)" />
              </el-alert>
            </div>
          </div>
        </div>
      </div>

      <el-drawer v-model="historyVisible" title="历史会话" size="380px">
        <div v-loading="historyLoading" class="history-list">
          <div v-if="!historyLoading && historyList.length === 0" class="history-empty">
            暂无历史会话
          </div>
          <div
            v-for="item in historyList"
            :key="item.id"
            class="history-item"
            @click="loadSession(item.id)"
          >
            <div class="history-item-top">
              <el-tag :type="item.status === 'completed' ? 'success' : 'warning'" size="small">
                {{ item.status === 'completed' ? '已完成' : '进行中' }}
              </el-tag>
              <span class="history-time">{{ formatTime(item.updated_at) }}</span>
            </div>
            <p class="history-title" v-html="renderedHtml(item.title)" />
            <p class="history-meta">第 {{ item.current_round + 1 }} 轮 · {{ hintLabels[item.hint_level] || '' }}</p>
          </div>
        </div>
      </el-drawer>
    </div>
  </AppLayout>
</template>

<style scoped>
.tutoring-page { max-width: 1100px; margin: 0 auto; }
.page-header { display: flex; align-items: center; justify-content: space-between; margin: 0 0 20px; }
.page-title { font-size: 22px; font-weight: 700; margin: 0; color: #1f2937; }

.history-list { display: flex; flex-direction: column; gap: 10px; }
.history-empty { text-align: center; color: #9ca3af; padding: 40px 0; font-size: 14px; }
.history-item {
  border: 1px solid #e5e7eb; border-radius: 10px; padding: 12px 14px;
  cursor: pointer; transition: all 0.15s;
}
.history-item:hover { border-color: #a78bfa; background: #f5f3ff; }
.history-item-top { display: flex; align-items: center; justify-content: space-between; margin-bottom: 6px; }
.history-time { font-size: 12px; color: #9ca3af; }
.history-title {
  margin: 0 0 4px; font-size: 14px; color: #1f2937; line-height: 1.5;
  overflow: hidden; text-overflow: ellipsis; display: -webkit-box; -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}
.history-meta { margin: 0; font-size: 12px; color: #6b7280; }

.input-section { display: flex; flex-direction: column; gap: 14px; }
.input-section :deep(.el-textarea__inner) { min-height: 100px; }
.upload-dropzone {
  border: 2px dashed #d1d5db; border-radius: 12px; padding: 24px;
  text-align: center; cursor: pointer; transition: all 0.2s;
}
.upload-dropzone:hover { border-color: #a78bfa; background: #f5f3ff; }
.upload-text { color: #6b7280; margin: 6px 0 2px; font-size: 14px; }
.upload-hint { color: #9ca3af; margin: 0; font-size: 12px; }
.image-preview { position: relative; border-radius: 12px; overflow: hidden; }
.image-preview img { max-width: 100%; max-height: 240px; display: block; }
.clear-btn { position: absolute; top: 6px; right: 6px; }
.options-row { display: flex; align-items: center; gap: 10px; margin: 4px 0; }
.mode-hint { font-size: 12px; color: #9ca3af; }
.submit-btn { width: 100%; font-size: 16px; }

.tutor-session { display: flex; flex-direction: column; gap: 14px; }
.session-header {
  display: flex; align-items: center; gap: 12px;
  padding: 10px 16px; background: #f9fafb; border-radius: 10px;
}
.session-round { font-size: 13px; color: #6b7280; flex: 1; }

.split-layout { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; min-height: 500px; }

.left-panel {
  background: #f9fafb; border-radius: 12px; padding: 20px;
  border: 1px solid #e5e7eb;
}
.question-image img { max-width: 100%; border-radius: 8px; }
.question-text h4 { font-size: 14px; color: #6b7280; margin: 0 0 8px; }
.question-text p { font-size: 15px; line-height: 1.8; color: #1f2937; white-space: pre-wrap; }

.right-panel {
  display: flex; flex-direction: column;
  border: 1px solid #e5e7eb; border-radius: 12px; overflow: hidden;
}

.chat-messages {
  flex: 1; overflow-y: auto; padding: 16px;
  display: flex; flex-direction: column; gap: 12px;
  max-height: 420px;
}
.chat-bubble { display: flex; gap: 10px; align-items: flex-start; }
.chat-bubble.user { flex-direction: row-reverse; }
.bubble-avatar {
  width: 32px; height: 32px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700; flex-shrink: 0;
}
.chat-bubble.ai .bubble-avatar { background: #ede9fe; color: #7c3aed; }
.chat-bubble.user .bubble-avatar { background: #dbeafe; color: #2563eb; }
.bubble-content {
  max-width: 80%; padding: 10px 14px; border-radius: 12px;
  font-size: 14px; line-height: 1.6;
}
.chat-bubble.ai .bubble-content { background: #f5f3ff; color: #374151; }
.chat-bubble.user .bubble-content { background: #eff6ff; color: #1e40af; }
.bubble-content p { margin: 0; white-space: pre-wrap; }
.typing { color: #9ca3af; font-style: italic; }

.chat-input-area { padding: 12px 16px; border-top: 1px solid #e5e7eb; }
.chat-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 8px; }

.answer-reveal { padding: 12px 16px; border-top: 1px solid #e5e7eb; }
.answer-reveal p { font-size: 14px; line-height: 1.8; color: #374151; white-space: pre-wrap; margin: 8px 0 0; }
</style>
