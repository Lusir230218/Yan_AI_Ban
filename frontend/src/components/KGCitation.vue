<script setup lang="ts">
/**
 * 阶段五·2C: 知识图谱引用 chip 组件。
 *
 * 用法:
 *   <KGCitation v-for="c in cited" :key="c.id" :concept="c" />
 *
 * 行为:
 * - 鼠标悬停 / 点击 → 异步加载概念详情（懒加载一次）
 * - 弹层显示：name + type + definition + 前置/后继/错因 + 用户掌握度
 * - 加载失败显示 "加载失败"，不阻塞 UI
 */
import { ref } from 'vue'
import type { CitedConcept } from '@/api/knowledgeGraph'
import { kgApi } from '@/api/knowledgeGraph'

const props = defineProps<{ concept: CitedConcept }>()

const detail = ref<any | null>(null)
const showDetail = ref(false)
const loading = ref(false)

async function loadDetail() {
  if (showDetail.value) {
    showDetail.value = false
    return
  }
  if (detail.value) {
    showDetail.value = true
    return
  }
  loading.value = true
  showDetail.value = true
  try {
    const r = await kgApi.getConcept(props.concept.id)
    detail.value = r
  } catch (e) {
    detail.value = { error: '加载失败' }
  } finally {
    loading.value = false
  }
}

const statusLabel: Record<string, string> = {
  weak: '🔴 薄弱',
  in_progress: '🟡 学习中',
  mastered: '🟢 已掌握',
}
</script>

<template>
  <span class="kg-cite" @mouseenter="loadDetail" @click.stop="loadDetail">
    <span class="kg-cite-name">[{{ concept.name }}]</span>
    <span v-if="showDetail" class="kg-detail" @click.stop>
      <span v-if="loading" class="kg-detail-loading">加载中…</span>
      <template v-else-if="detail?.error">
        <span class="kg-detail-error">{{ detail.error }}</span>
      </template>
      <template v-else-if="detail?.concept">
        <!-- 标题 + 类型 -->
        <div class="kg-detail-head">
          <strong>{{ detail.concept.name }}</strong>
          <span class="kg-detail-type">{{ detail.concept.type }}</span>
        </div>

        <!-- 定义 -->
        <div v-if="detail.concept.definition" class="kg-detail-def">
          {{ detail.concept.definition }}
        </div>
        <div v-else class="kg-detail-empty">（暂无定义）</div>

        <!-- 前置知识 -->
        <div v-if="detail.prerequisites?.length" class="kg-detail-section">
          <div class="kg-detail-label">🔼 前置知识（{{ detail.prerequisites.length }}）</div>
          <div class="kg-detail-links">
            <span v-for="p in detail.prerequisites" :key="p.id" class="kg-link">
              {{ p.name }} <span class="kg-link-type">{{ p.type }}</span>
            </span>
          </div>
        </div>

        <!-- 后继知识 -->
        <div v-if="detail.next_concepts?.length" class="kg-detail-section">
          <div class="kg-detail-label">🔽 后继知识（{{ detail.next_concepts.length }}）</div>
          <div class="kg-detail-links">
            <span v-for="p in detail.next_concepts" :key="p.id" class="kg-link">
              {{ p.name }} <span class="kg-link-type">{{ p.type }}</span>
            </span>
          </div>
        </div>

        <!-- 常见错因 -->
        <div v-if="detail.common_mistakes?.length" class="kg-detail-section">
          <div class="kg-detail-label">⚠️ 常见错因（{{ detail.common_mistakes.length }}）</div>
          <div class="kg-detail-links">
            <span v-for="p in detail.common_mistakes" :key="p.id" class="kg-link kg-link-warn">
              {{ p.name }}
            </span>
          </div>
        </div>

        <!-- 掌握度 -->
        <div v-if="detail.user_state" class="kg-detail-state">
          你：{{ statusLabel[detail.user_state.status] || detail.user_state.status }}
        </div>
        <div v-else-if="detail.concept.pg_kp_id !== null && detail.concept.pg_kp_id !== undefined" class="kg-detail-empty">
          （暂无掌握度数据 — 做完相关题后会记录）
        </div>
      </template>
    </span>
  </span>
</template>

<style scoped>
.kg-cite {
  position: relative;
  display: inline-block;
  color: #4a90e2;
  cursor: pointer;
  padding: 1px 4px;
  border-radius: 3px;
  background: #eef6ff;
  margin: 0 2px;
  font-size: 0.95em;
  user-select: none;
}
.kg-cite:hover { background: #dceeff; }
.kg-cite-name { line-height: 1.4; }

.kg-detail {
  position: absolute;
  bottom: calc(100% + 6px);
  left: 0;
  background: white;
  border: 1px solid #ddd;
  border-radius: 6px;
  padding: 10px 12px;
  min-width: 280px;
  max-width: 420px;
  z-index: 100;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.08);
  font-size: 0.85em;
  line-height: 1.5;
  color: #374151;
  cursor: default;
  text-align: left;
}

.kg-detail-head {
  display: flex; gap: 8px; align-items: center; margin-bottom: 6px;
  border-bottom: 1px solid #f3f4f6; padding-bottom: 6px;
}
.kg-detail-type {
  background: #f3f4f6;
  color: #6b7280;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 0.85em;
}
.kg-detail-def { color: #4b5563; margin: 4px 0 8px; line-height: 1.6; }
.kg-detail-empty { color: #9ca3af; font-style: italic; font-size: 0.9em; margin: 4px 0; }

.kg-detail-section { margin-top: 6px; }
.kg-detail-label {
  color: #6b7280;
  font-size: 0.8em;
  margin-bottom: 3px;
  font-weight: 500;
}
.kg-detail-links {
  display: flex; flex-wrap: wrap; gap: 3px;
}
.kg-link {
  background: #f3f4f6;
  color: #4b5563;
  padding: 1px 6px;
  border-radius: 3px;
  font-size: 0.85em;
  cursor: default;
}
.kg-link:hover { background: #e5e7eb; }
.kg-link-type {
  color: #9ca3af;
  font-size: 0.75em;
  margin-left: 2px;
}
.kg-link-warn {
  background: #fef3c7;
  color: #92400e;
}

.kg-detail-state {
  color: #1f2937;
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px solid #f3f4f6;
  font-size: 0.9em;
  font-weight: 500;
}
.kg-detail-loading { color: #9ca3af; font-style: italic; }
.kg-detail-error { color: #ef4444; }
</style>