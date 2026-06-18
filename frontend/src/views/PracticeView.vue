<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import AppLayout from '@/components/AppLayout.vue'
import { questionApi } from '@/api/questions'
import type { QuestionResponse, AnswerResult, KnowledgePointTree } from '@/types'
import { renderMath } from '@/utils/math'
import { ArrowLeft, Collection } from '@element-plus/icons-vue'

const questions = ref<QuestionResponse[]>([])
const loading = ref(true)
const selectedId = ref<number | null>(null)
const selectedAnswers = ref<string[]>([])
const submitting = ref(false)
const result = ref<AnswerResult | null>(null)
const subjectFilter = ref<string>('')
const variantFilter = ref<string>('')
const chapterFilter = ref<string>('')
const knowledgeTree = ref<KnowledgePointTree[]>([])
const startTime = ref(0)
const practiceStarted = ref(false)
const pendingSubject = ref('')
const dialogVisible = computed({
  get: () => !!pendingSubject.value,
  set: (v) => { if (!v) pendingSubject.value = '' }
})

const subjects = ['数学', '英语', '政治']
const subjectColors: Record<string, string> = { '数学': '#4f46e5', '英语': '#059669', '政治': '#d97706' }
const subjectEmoji: Record<string, string> = { '数学': '📐', '英语': '🔤', '政治': '🏛️' }
const variantLabel: Record<string, string> = {
  '数一': '数学一', '数二': '数学二', '数三': '数学三',
  '英一': '英语一', '英二': '英语二',
}

const current = computed(() => questions.value.find(q => q.id === selectedId.value))
const optionsList = computed(() => {
  if (!current.value) return []
  try { return JSON.parse(current.value.options) as string[] } catch { return [] }
})
const isMulti = computed(() => current.value?.question_type === 'multi_choice')
const hasOptions = computed(() => {
  const t = current.value?.question_type
  return t === 'choice' || t === 'multi_choice' || t === 'single_choice' || t === 'true_false'
})
const fillBlankMode = computed(() => current.value?.question_type === 'fill_blank')
const essayMode = computed(() =>
  ['essay', 'material_analysis', 'translation', 'writing'].includes(current.value?.question_type || '')
)
const groupQuestions = computed(() => {
  if (!current.value?.group_id) return []
  return questions.value.filter(q => q.group_id === current.value!.group_id).sort((a, b) => (a.group_order ?? 0) - (b.group_order ?? 0))
})
const groupedQuestions = computed(() => {
  const map: Record<string, QuestionResponse[]> = {}
  for (const q of questions.value) {
    const key = q.knowledge_point?.name || '未分类'
    if (!map[key]) map[key] = []
    map[key].push(q)
  }
  return Object.entries(map)
})
const typeLabel: Record<string, string> = {
  choice: '单选', single_choice: '单选', multi_choice: '多选', true_false: '判断',
  fill_blank: '填空', essay: '解答', material_analysis: '材料分析', translation: '翻译', writing: '写作',
}
const variantOptions = computed(() => {
  if (subjectFilter.value === '数学') return ['数一', '数二', '数三'].map(v => ({ label: variantLabel[v], value: v }))
  if (subjectFilter.value === '英语') return ['英一', '英二'].map(v => ({ label: variantLabel[v], value: v }))
  return []
})

function examVariantLabel(subject: string) {
  if (subject === '数学') return ['数一', '数二', '数三']
  if (subject === '英语') return ['英一', '英二']
  return []
}
onMounted(() => {})
async function selectQuestion(id: number) {
  selectedId.value = id; selectedAnswers.value = []; result.value = null; startTime.value = Date.now()
}
function toggleAnswer(opt: string) {
  const letter = opt.charAt(0)
  if (isMulti.value) {
    const idx = selectedAnswers.value.indexOf(letter)
    if (idx >= 0) selectedAnswers.value.splice(idx, 1)
    else selectedAnswers.value.push(letter)
  } else { selectedAnswers.value = [letter] }
}
function isSelected(opt: string) { return selectedAnswers.value.includes(opt.charAt(0)) }
function stemPreview(stem: string) { return stem.replace(/\\?\$.*?\$\$?/g, '').slice(0, 30) }
async function handleSubmit() {
  if (!current.value || selectedAnswers.value.length === 0) return
  submitting.value = true
  try {
    const duration = Math.floor((Date.now() - startTime.value) / 1000)
    const res = await questionApi.submitAnswer(current.value.id, {
      answer: selectedAnswers.value.sort().join(''),
      duration_seconds: duration, subject: current.value.subject,
    })
    result.value = res.data
  } finally { submitting.value = false }
}
async function filterAll() {
  loading.value = true
  try {
    const params: Record<string, any> = {}
    if (subjectFilter.value) params.subject = subjectFilter.value
    if (variantFilter.value) params.exam_variant = variantFilter.value
    if (chapterFilter.value) params.knowledge_point_id = Number(chapterFilter.value)
    const res = await questionApi.listQuestions(params)
    questions.value = res.data; selectedId.value = null; result.value = null
  } finally { loading.value = false }
}
async function loadKnowledgeTree() {
  try {
    const res = await questionApi.getKnowledgeTree({
      subject: subjectFilter.value, exam_variant: variantFilter.value || undefined,
    })
    knowledgeTree.value = res.data
  } catch { knowledgeTree.value = [] }
}
async function variantChanged() { chapterFilter.value = ''; await loadKnowledgeTree(); filterAll() }
async function subjectChanged() { variantFilter.value = ''; chapterFilter.value = ''; await loadKnowledgeTree(); filterAll() }
function startPractice(subject: string) { pendingSubject.value = subject }
function confirmStart() {
  subjectFilter.value = pendingSubject.value; practiceStarted.value = true; pendingSubject.value = ''
  loadKnowledgeTree(); filterAll()
}
function goBack() {
  practiceStarted.value = false; questions.value = []; selectedId.value = null
  result.value = null; variantFilter.value = ''; chapterFilter.value = ''
}
</script>

<template>
  <AppLayout>
    <!-- ════ 科目选择页 ════ -->
    <div v-if="!practiceStarted" class="landing">
      <dv-border-box-8>
        <div class="landing-content">
          <h1 class="landing-title">题库练习</h1>
          <p class="landing-desc">选择科目，精准刷题</p>
          <div class="landing-subjects">
            <button
              v-for="s in subjects" :key="s"
              class="subject-hero-btn"
              :style="{ '--color': subjectColors[s] }"
              @click="startPractice(s)"
            >
              <span class="hero-emoji">{{ subjectEmoji[s] }}</span>
              <span class="hero-label">{{ s }}</span>
            </button>
          </div>
        </div>
      </dv-border-box-8>
    </div>

    <!-- ════ 确认弹窗 ════ -->
    <el-dialog v-model="dialogVisible" title="确认开始练习" width="400" align-center>
      <p style="text-align:center;font-size:15px;color:#6b7280;">
        确定要开始 <strong style="color:#4f46e5;">{{ pendingSubject }}</strong> 的练习吗？
      </p>
      <template #footer>
        <el-button @click="pendingSubject = ''">取消</el-button>
        <el-button type="primary" @click="confirmStart">确定开始</el-button>
      </template>
    </el-dialog>

    <!-- ════ Header 插槽 ════ -->
    <template #header-actions>
      <template v-if="practiceStarted">
        <el-tag :color="subjectColors[subjectFilter]" effect="dark" size="large">
          {{ subjectFilter }}
        </el-tag>
        <el-button :icon="ArrowLeft" text @click="goBack">返回科目</el-button>
      </template>
    </template>

    <!-- ════ 练习页 ════ -->
    <template v-if="practiceStarted">
      <div class="practice-layout">
        <aside class="sidebar-panel">
          <div class="panel-inner">
            <div class="panel-hd">
              <span class="panel-title">题目列表</span>
              <span v-if="!loading" class="panel-count">{{ questions.length }} 题</span>
            </div>
            <div class="panel-filters">
              <el-select v-model="variantFilter" placeholder="考试类别" clearable size="small" @change="variantChanged">
                <el-option v-for="vo in variantOptions" :key="vo.value" :label="vo.label" :value="vo.value" />
              </el-select>
              <el-select v-model="chapterFilter" placeholder="全部章节" clearable size="small" @change="filterAll">
                <el-option value="">全部章节</el-option>
                <el-option-group v-for="branch in knowledgeTree" :key="branch.id || branch.name" :label="branch.name">
                  <template v-for="ch in branch.children" :key="ch.id || ch.name">
                    <el-option :label="ch.name" :value="String(ch.id || '')" />
                    <el-option
                      v-for="sub in ch.children"
                      :key="'s' + (sub.id || sub.name)"
                      :label="'　' + sub.name"
                      :value="String(sub.id || '')"
                    />
                  </template>
                </el-option-group>
              </el-select>
            </div>
            <div v-if="loading" class="panel-loading">
              <el-icon class="is-loading" :size="20"><Collection /></el-icon>
            </div>
            <div v-else class="panel-list">
              <template v-for="[chapter, qs] in groupedQuestions" :key="chapter">
                <div class="chapter-divider">{{ chapter }}</div>
                <button
                  v-for="q in qs" :key="q.id"
                  :class="['q-item', { active: q.id === selectedId }]"
                  @click="selectQuestion(q.id)"
                >
                  <el-tag size="small" type="info">{{ typeLabel[q.question_type] || q.question_type }}</el-tag>
                  <span v-if="q.exam_variant" class="item-var">{{ q.exam_variant }}</span>
                  <span class="item-stem">{{ stemPreview(q.stem) }}...</span>
                </button>
              </template>
              <div v-if="questions.length === 0" class="empty-hint">暂无题目</div>
            </div>
          </div>
        </aside>

        <div class="answer-area">
          <div v-if="!current" class="placeholder-hint">
            <el-result icon="info" title="选择题目" sub-title="请从左侧列表选择一道题目开始练习" />
          </div>
          <template v-else>
            <div v-if="current.group" class="group-card">
              <div class="group-card-hd">
                <el-icon :size="16"><Collection /></el-icon>
                <span>{{ current.group.title || '阅读材料' }}</span>
              </div>
              <div class="group-card-body" v-html="renderMath(current.group.content)"></div>
            </div>
            <div v-if="current.images" class="q-images-row">
              <el-image
                v-for="(url, i) in JSON.parse(current.images || '[]')"
                :key="i" :src="url" class="q-img"
                fit="contain" preview-teleported
              />
            </div>
            <el-card class="q-card" shadow="hover">
              <div class="q-meta-row">
                <el-tag>{{ current.subject }}</el-tag>
                <el-tag v-if="current.knowledge_point" type="success">{{ current.knowledge_point.name }}</el-tag>
                <el-tag v-if="current.exam_variant" type="warning">{{ variantLabel[current.exam_variant] || current.exam_variant }}</el-tag>
                <el-tag type="info">{{ typeLabel[current.question_type] || current.question_type }}</el-tag>
                <span class="stars">{{ '⭐'.repeat(current.difficulty) }}</span>
              </div>
              <div class="q-stem" v-html="renderMath(current.stem)"></div>
              <div v-if="hasOptions" class="q-options">
                <el-button
                  v-for="opt in optionsList" :key="opt"
                  :type="isSelected(opt) ? 'primary' : 'default'"
                  :plain="!isSelected(opt)" size="large" class="opt-btn"
                  :disabled="!!result" @click="toggleAnswer(opt)"
                >
                  <span v-html="renderMath(opt)" />
                </el-button>
              </div>
              <div v-if="fillBlankMode" class="input-row">
                <el-input v-model="selectedAnswers[0]" placeholder="请输入你的答案" :disabled="!!result" size="large" />
              </div>
              <div v-if="essayMode" class="input-row">
                <el-input v-model="selectedAnswers[0]" type="textarea" :rows="6" placeholder="请输入你的答案..." :disabled="!!result" />
              </div>
              <div v-if="!result" class="submit-row">
                <el-button
                  type="primary" size="large" :loading="submitting"
                  :disabled="selectedAnswers.length === 0 || !selectedAnswers[0]"
                  @click="handleSubmit"
                >提交答案</el-button>
              </div>
            </el-card>
            <div v-if="groupQuestions.length > 1" class="group-nav">
              <span class="group-nav-label">本组题目：</span>
              <el-button
                v-for="gq in groupQuestions" :key="gq.id"
                :type="gq.id === current.id ? 'primary' : 'default'"
                size="small" @click="selectQuestion(gq.id)"
              >{{ gq.group_order || '?' }}</el-button>
            </div>
            <div v-if="result" class="feedback-card">
              <el-result
                :icon="result.is_correct ? 'success' : 'error'"
                :title="result.is_correct ? '回答正确！' : '回答错误'"
                :sub-title="result.is_correct ? '' : '正确答案：' + result.correct_answer"
              >
                <template v-if="result.explanation" #extra>
                  <el-card shadow="never">
                    <div class="explanation-text" v-html="renderMath(result.explanation)"></div>
                  </el-card>
                </template>
                <template #default>
                  <el-button type="primary" @click="result = null; selectedAnswers = []">继续练习</el-button>
                </template>
              </el-result>
            </div>
          </template>
        </div>
      </div>
    </template>
  </AppLayout>
</template>

<style scoped>
/* ── Landing ── */
.landing {
  display: flex; align-items: center; justify-content: center;
  min-height: calc(100vh - 180px);
}
.landing-wrapper { width: 640px; }
.landing-content { padding: 60px 40px 48px; text-align: center; }
.landing-title {
  font-size: 32px; font-weight: 800;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text; -webkit-text-fill-color: transparent;
  background-clip: text; margin: 0 0 8px;
}
.landing-desc { font-size: 15px; color: #9ca3af; margin: 0 0 40px; }
.landing-subjects { display: flex; gap: 24px; justify-content: center; }
.subject-hero-btn {
  width: 170px; height: 160px; border: 2px solid #e5e7eb;
  background: #fff; border-radius: 20px; cursor: pointer;
  display: flex; flex-direction: column; align-items: center;
  justify-content: center; gap: 12px; transition: all 0.25s;
}
.subject-hero-btn:hover {
  border-color: var(--color);
  box-shadow: 0 8px 30px rgba(0,0,0,0.08);
  transform: translateY(-4px);
}
.hero-emoji { font-size: 42px; }
.hero-label { font-size: 20px; font-weight: 700; color: #1f2937; }

/* ── Practice Layout ── */
.practice-layout { display: flex; gap: 20px; height: calc(100vh - 120px); }

/* ── Sidebar ── */
.sidebar-panel {
  width: 290px; min-width: 290px;
  background: #fff; border-radius: 16px; overflow: hidden;
  display: flex; flex-direction: column;
  box-shadow: 0 1px 3px rgba(0,0,0,0.04);
}
.panel-inner { display: flex; flex-direction: column; height: 100%; }
.panel-hd {
  padding: 18px 16px 12px; display: flex; align-items: center; justify-content: space-between;
}
.panel-title { font-size: 16px; font-weight: 700; color: #1f2937; }
.panel-count { font-size: 12px; color: #9ca3af; background: #f3f4f6; padding: 2px 10px; border-radius: 10px; }
.panel-filters { display: flex; flex-direction: column; gap: 8px; padding: 0 12px 8px; }
.panel-loading { display: flex; justify-content: center; padding: 40px 0; }
.panel-list { flex: 1; overflow-y: auto; padding: 0 8px 8px; }
.chapter-divider {
  font-size: 11px; font-weight: 700; color: #9ca3af; padding: 10px 12px 4px;
  text-transform: uppercase; letter-spacing: 1px;
}
.q-item {
  display: flex; align-items: center; gap: 6px; width: 100%;
  text-align: left; padding: 10px 12px; border: none;
  background: transparent; border-radius: 10px; cursor: pointer;
  font-size: 13px; transition: all 0.15s;
}
.q-item:hover { background: #f3f4f6; }
.q-item.active { background: #eef2ff; }
.item-var {
  font-size: 10px; background: #dbeafe; color: #2563eb;
  padding: 0 5px; border-radius: 4px; white-space: nowrap;
}
.item-stem { color: #374151; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.empty-hint { padding: 32px; text-align: center; color: #d1d5db; }

/* ── Answer Area ── */
.answer-area { flex: 1; display: flex; flex-direction: column; gap: 16px; overflow-y: auto; }
.placeholder-hint { flex: 1; display: flex; align-items: center; justify-content: center; }

/* ── Group ── */
.group-card {
  background: #fffbeb; border-radius: 14px; overflow: hidden; border: 1px solid #fde68a;
}
.group-card-hd {
  display: flex; align-items: center; gap: 8px;
  padding: 12px 18px; background: #fef3c7;
  font-size: 14px; font-weight: 600; color: #92400e;
}
.group-card-body { padding: 16px 18px; font-size: 14px; line-height: 1.8; color: #78350f; white-space: pre-wrap; }

/* ── Question Card ── */
.q-card { border-radius: 14px; }
.q-card :deep(.el-card__body) { padding: 28px; }
.q-meta-row { display: flex; gap: 8px; margin-bottom: 18px; flex-wrap: wrap; align-items: center; }
.stars { font-size: 12px; margin-left: auto; }
.q-stem { font-size: 16px; line-height: 1.8; color: #1f2937; margin-bottom: 24px; white-space: pre-wrap; }
.q-options { display: flex; flex-direction: column; gap: 12px; margin-bottom: 20px; }
.opt-btn { justify-content: flex-start; text-align: left; white-space: normal; height: auto; min-height: 44px; }
.input-row { margin-bottom: 20px; }
.submit-row { text-align: center; }

/* ── Group Nav ── */
.group-nav { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.group-nav-label { font-size: 13px; color: #6b7280; font-weight: 600; }

/* ── Feedback ── */
.feedback-card { background: #fff; border-radius: 16px; padding: 24px; box-shadow: 0 1px 3px rgba(0,0,0,0.04); }
.explanation-text { font-size: 14px; line-height: 1.7; color: #6b7280; }

/* ── Images ── */
.q-images-row { display: flex; gap: 10px; flex-wrap: wrap; }
.q-img { max-width: 100%; border-radius: 10px; max-height: 300px; }

:deep(.el-result__title) { font-size: 20px !important; }
</style>
