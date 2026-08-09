<script setup lang="ts">
/**
 * 阶段五·2C: AI 问答面板 — 基于知识图谱检索 + 引用 + 👍/👎。
 *
 * 行为：
 * - 用户输入 query → POST /kg/search → 流式返回 answer + cited
 * - 每条 AI 回答后挂 [引用] chip 列表（hover/点击查看概念详情）
 * - 每条 AI 回答可点赞 / 点踩，写 feedback_kg_answer（rating=1 必传 cited）
 * - 加载中显示打字提示，错误给兜底提示
 *
 * 集成位置：本组件可作为独立 widget 嵌入 TutoringView 或 Dashboard。
 *         通过 emit('fallback-detected') 暴露兜底事件供父组件做兜底引导。
 */
import { ref, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { ChatLineRound, Promotion } from '@element-plus/icons-vue'
import { kgApi, type CitedConcept, type RetrievedNode } from '@/api/knowledgeGraph'
import KGCitation from './KGCitation.vue'

interface Message {
  role: 'user' | 'ai'
  text: string
  cited?: CitedConcept[]
  seeds?: RetrievedNode[]
  expanded?: RetrievedNode[]
  loading?: boolean
  error?: boolean
  fallback?: boolean
  usedTokens?: number
}

const messages = ref<Message[]>([])
const userInput = ref('')
const sending = ref(false)
const chatContainer = ref<HTMLElement | null>(null)

const emit = defineEmits<{
  (e: 'fallback-detected', query: string): void
  (e: 'feedback-submitted', rating: -1 | 1): void
}>()

async function scrollToBottom() {
  await nextTick()
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

async function send() {
  const text = userInput.value.trim()
  if (!text || sending.value) return

  const userMsg: Message = { role: 'user', text }
  messages.value.push(userMsg)
  userInput.value = ''
  await scrollToBottom()

  const aiMsg: Message = { role: 'ai', text: '', loading: true }
  messages.value.push(aiMsg)

  sending.value = true
  try {
    const r = await kgApi.search(text)
    const data = r.data
    aiMsg.text = data.answer
    aiMsg.cited = data.cited
    aiMsg.seeds = data.seeds
    aiMsg.expanded = data.expanded
    aiMsg.fallback = data.fallback
    aiMsg.usedTokens = data.used_token_estimate
    aiMsg.loading = false
    if (data.fallback) emit('fallback-detected', text)
  } catch (e: any) {
    aiMsg.text = '（AI 出错了，稍后再试）'
    aiMsg.error = true
    aiMsg.loading = false
    ElMessage.error(e?.response?.data?.detail || 'AI 调用失败')
  } finally {
    sending.value = false
    await scrollToBottom()
  }
}

async function rate(idx: number, rating: -1 | 1) {
  const m = messages.value[idx]
  if (!m || m.role !== 'ai') return
  // 找到对应的 user 消息（紧邻上一条）
  const userMsg = [...messages.value.slice(0, idx)].reverse().find(x => x.role === 'user')
  try {
    await kgApi.submitFeedback({
      query: userMsg?.text ?? '',
      answer: m.text,
      cited_concepts: m.cited ?? [],
      rating,
    })
    ElMessage.success(rating === 1 ? '已点赞' : '已记录反馈')
    emit('feedback-submitted', rating)
  } catch (e: any) {
    // rating=1 + 无 cited 会被后端 400 — 给前端友好提示
    const detail = e?.response?.data?.detail || ''
    if (rating === 1 && detail.includes('cited')) {
      ElMessage.warning('请先确保回答中至少引用了一条知识')
    } else {
      ElMessage.error('反馈提交失败')
    }
  }
}

function reset() {
  messages.value = []
  userInput.value = ''
}
</script>

<template>
  <div class="ai-chat-panel">
    <div class="chat-header">
      <el-icon :size="20" color="#4a90e2"><ChatLineRound /></el-icon>
      <span class="chat-title">AI 知识问答</span>
      <el-button v-if="messages.length" text size="small" @click="reset">清空</el-button>
    </div>

    <div ref="chatContainer" class="chat-messages">
      <div v-if="messages.length === 0" class="chat-empty">
        <p>有什么想问的？例如：</p>
        <ul>
          <li>「如何学换元积分法？」</li>
          <li>「极限和连续有什么关系？」</li>
          <li>「我的薄弱点是什么？」</li>
        </ul>
      </div>

      <div v-for="(m, i) in messages" :key="i" :class="['msg', m.role]">
        <div class="msg-avatar">
          {{ m.role === 'ai' ? 'AI' : '我' }}
        </div>
        <div class="msg-body">
          <div class="msg-text" :class="{ error: m.error }">
            <template v-if="m.loading">
              <span class="typing">思考中…</span>
            </template>
            <template v-else>
              {{ m.text }}
            </template>
          </div>

          <!-- 引用 chip 列表（LLM 主动 cite 的）-->
          <div v-if="m.cited && m.cited.length && !m.loading" class="cited-row">
            <KGCitation v-for="c in m.cited" :key="c.id" :concept="c" />
          </div>

          <!-- 召回全貌：种子 + 扩展 -->
          <details v-if="!m.loading && ((m.seeds?.length ?? 0) + (m.expanded?.length ?? 0)) > 0" class="context-details">
            <summary class="context-summary">
              🔍 召回 {{ (m.seeds?.length ?? 0) + (m.expanded?.length ?? 0) }} 个相关概念
              <span class="context-breakdown">
                ({{ m.seeds?.length ?? 0 }} 种子 + {{ m.expanded?.length ?? 0 }} 扩展)
              </span>
            </summary>
            <div class="context-body">
              <div v-if="m.seeds?.length" class="context-group">
                <div class="context-label">📌 种子（向量召回 top-{{ m.seeds.length }}）</div>
                <div class="context-chips">
                  <span v-for="n in m.seeds" :key="n.id" class="ctx-node seed-node">
                    {{ n.name }}
                    <span class="ctx-meta">sim {{ n.vector_score }} · conf {{ n.confidence }}</span>
                  </span>
                </div>
              </div>
              <div v-if="m.expanded?.length" class="context-group">
                <div class="context-label">🔗 扩展（1 跳图）</div>
                <div class="context-chips">
                  <span v-for="n in m.expanded" :key="n.id" class="ctx-node expanded-node">
                    {{ n.name }}
                    <span class="ctx-meta">conf {{ n.confidence }}</span>
                  </span>
                </div>
              </div>
            </div>
          </details>

          <!-- fallback 提示 -->
          <div v-if="m.fallback && !m.loading" class="fallback-tip">
            💡 图谱暂未覆盖，可以试试相关考点关键词
          </div>

          <!-- 评分 -->
          <div v-if="m.role === 'ai' && !m.loading && !m.error" class="rating-row">
            <span v-if="m.usedTokens !== undefined" class="token-hint" :title="`本次 RAG prompt context 占用 ${m.usedTokens} / 3000 tokens`">
              📊 {{ m.usedTokens }} / 3000
            </span>
            <button class="rate-btn" @click="rate(i, 1)" title="有用">👍</button>
            <button class="rate-btn" @click="rate(i, -1)" title="没帮助">👎</button>
          </div>
        </div>
      </div>
    </div>

    <div class="chat-input-area">
      <el-input
        v-model="userInput"
        type="textarea"
        :rows="2"
        placeholder="输入问题…（Enter 发送，Shift+Enter 换行）"
        :disabled="sending"
        @keydown.enter.exact.prevent="send"
      />
      <div class="chat-actions">
        <el-button
          type="primary"
          :icon="Promotion"
          :disabled="!userInput.trim() || sending"
          :loading="sending"
          @click="send"
        >
          发送
        </el-button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ai-chat-panel {
  display: flex;
  flex-direction: column;
  height: 600px;
  max-height: 80vh;
  background: #fff;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
  overflow: hidden;
}

.chat-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-bottom: 1px solid #e5e7eb;
  background: #f9fafb;
}
.chat-title { font-weight: 600; font-size: 15px; color: #1f2937; flex: 1; }

.chat-messages {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.chat-empty {
  text-align: center;
  color: #9ca3af;
  padding: 40px 16px;
  font-size: 13px;
}
.chat-empty ul { text-align: left; display: inline-block; padding-left: 16px; }
.chat-empty li { margin: 4px 0; }

.msg {
  display: flex;
  gap: 10px;
  align-items: flex-start;
}
.msg.user { flex-direction: row-reverse; }

.msg-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  flex-shrink: 0;
}
.msg.ai .msg-avatar { background: #ede9fe; color: #7c3aed; }
.msg.user .msg-avatar { background: #dbeafe; color: #2563eb; }

.msg-body { max-width: 75%; display: flex; flex-direction: column; gap: 4px; }
.msg-text {
  padding: 10px 14px;
  border-radius: 12px;
  font-size: 14px;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-word;
}
.msg.ai .msg-text { background: #f5f3ff; color: #374151; }
.msg.user .msg-text { background: #eff6ff; color: #1e40af; }
.msg-text.error { color: #ef4444; background: #fef2f2; }
.typing { color: #9ca3af; font-style: italic; }

.cited-row {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
  padding-left: 4px;
}

/* 召回全貌（折叠面板）*/
.context-details {
  margin-top: 4px;
  font-size: 12px;
}
.context-summary {
  cursor: pointer;
  color: #6b7280;
  user-select: none;
  padding: 4px 6px;
  border-radius: 4px;
}
.context-summary:hover { background: #f3f4f6; color: #4b5563; }
.context-breakdown { color: #9ca3af; margin-left: 4px; font-size: 11px; }
.context-body { padding: 6px 8px; }
.context-group { margin-bottom: 8px; }
.context-label { color: #6b7280; margin-bottom: 4px; font-weight: 500; }
.context-chips { display: flex; flex-wrap: wrap; gap: 4px; }
.ctx-node {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 8px;
  border-radius: 4px;
  font-size: 12px;
}
.seed-node { background: #fef3c7; color: #92400e; border: 1px solid #fde68a; }
.expanded-node { background: #e0e7ff; color: #3730a3; border: 1px solid #c7d2fe; }
.ctx-meta { font-size: 10px; color: #6b7280; font-family: ui-monospace, monospace; }

.fallback-tip {
  font-size: 12px;
  color: #b45309;
  background: #fef3c7;
  padding: 4px 10px;
  border-radius: 6px;
  margin-top: 2px;
}

.rating-row {
  display: flex;
  gap: 4px;
  padding-left: 4px;
  opacity: 0.5;
  transition: opacity 0.2s;
}
.msg-body:hover .rating-row { opacity: 1; }
.rate-btn {
  background: transparent;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  padding: 2px 8px;
  font-size: 13px;
  cursor: pointer;
}
.rate-btn:hover { background: #f9fafb; }

.token-hint {
  font-size: 11px;
  color: #9ca3af;
  margin-right: auto;
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  cursor: help;
}

.chat-input-area {
  padding: 12px 16px;
  border-top: 1px solid #e5e7eb;
  background: #fafafa;
}
.chat-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 8px;
}
</style>