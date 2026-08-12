<script setup lang="ts">
/**
 * 阶段五·2D 飞轮 admin 后台
 *
 * - 顶部 stats：概念数 / 活跃 / disputed / 平均 confidence / 7d 反馈 / queue 大小
 * - review queue 表格：每条可批准 / 拒绝
 */
import { onMounted, ref } from 'vue'
import client from '@/api/client'

interface QueueItem {
  id: number
  kind: 'cycle' | 'low_conf_relation'
  from_id: string
  from_name: string
  rel: string
  conf: number
  reason: string
  to_id: string
  to_name: string
  created_at: string | null
}

interface KgStats {
  concepts: {
    total: number
    active: number
    disputed: number
    archived: number
    avg_conf: number
  }
  feedback_7d: number
  review_queue_size: number
}

const queue = ref<QueueItem[]>([])
const stats = ref<KgStats | null>(null)
const loading = ref(false)
const errMsg = ref<string | null>(null)

async function load() {
  loading.value = true
  errMsg.value = null
  try {
    const [q, s] = await Promise.all([
      client.get<QueueItem[]>('/kg/admin/flywheel/review-queue'),
      client.get<KgStats>('/kg/admin/flywheel/stats'),
    ])
    queue.value = q.data
    stats.value = s.data
  } catch (e: any) {
    errMsg.value = e?.response?.data?.detail || e?.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function approve(id: number) {
  await client.post('/kg/admin/flywheel/approve-review', { queue_id: id })
  await load()
}
async function reject(id: number) {
  if (!confirm('确定要拒绝并删除这条 Neo4j 关系吗？')) return
  await client.post('/kg/admin/flywheel/reject-review', { queue_id: id })
  await load()
}

onMounted(load)
</script>

<template>
  <div class="kg-admin">
    <header class="page-head">
      <h1>知识图谱运营</h1>
      <button class="refresh" :disabled="loading" @click="load">
        {{ loading ? '加载中…' : '刷新' }}
      </button>
    </header>

    <p v-if="errMsg" class="err">{{ errMsg }}</p>

    <!-- 概览 -->
    <section v-if="stats" class="stats">
      <div class="stat">
        <span class="label">总概念</span>
        <span class="value">{{ stats.concepts.total }}</span>
      </div>
      <div class="stat">
        <span class="label">活跃</span>
        <span class="value text-green">{{ stats.concepts.active }}</span>
      </div>
      <div class="stat">
        <span class="label">Disputed</span>
        <span class="value text-yellow">{{ stats.concepts.disputed }}</span>
      </div>
      <div class="stat">
        <span class="label">已归档</span>
        <span class="value text-grey">{{ stats.concepts.archived }}</span>
      </div>
      <div class="stat">
        <span class="label">平均 confidence</span>
        <span class="value">{{ stats.concepts.avg_conf.toFixed(2) }}</span>
      </div>
      <div class="stat">
        <span class="label">7 天反馈</span>
        <span class="value">{{ stats.feedback_7d }}</span>
      </div>
    </section>

    <!-- Review Queue -->
    <section class="queue-section">
      <h2>待 review ({{ stats?.review_queue_size ?? queue.length }})</h2>
      <p v-if="queue.length === 0" class="empty">暂无待 review 项。</p>
      <table v-else>
        <thead>
          <tr>
            <th>类型</th>
            <th>From</th>
            <th>关系</th>
            <th>To</th>
            <th>Conf</th>
            <th>原因</th>
            <th>操作</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="item in queue" :key="item.id">
            <td>
              <span :class="['badge', item.kind]">
                {{ item.kind === 'cycle' ? 'cycle' : 'low_conf' }}
              </span>
            </td>
            <td>
              <div class="concept">{{ item.from_name }}</div>
              <div class="concept-id">{{ item.from_id }}</div>
            </td>
            <td>{{ item.rel }}</td>
            <td>
              <div class="concept">{{ item.to_name }}</div>
              <div class="concept-id">{{ item.to_id }}</div>
            </td>
            <td>{{ item.conf.toFixed(2) }}</td>
            <td>{{ item.reason }}</td>
            <td>
              <button class="ok" @click="approve(item.id)">批准</button>
              <button class="bad" @click="reject(item.id)">拒绝</button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<style scoped>
.kg-admin {
  max-width: 1100px;
  margin: 0 auto;
  padding: 24px;
}
.page-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.page-head h1 {
  margin: 0;
  font-size: 1.6em;
}
.refresh {
  padding: 6px 14px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  background: #fff;
  cursor: pointer;
}
.refresh:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.err {
  color: #f56c6c;
  padding: 8px 12px;
  background: #fef0f0;
  border-radius: 4px;
}
.stats {
  display: flex;
  gap: 12px;
  margin-bottom: 24px;
  flex-wrap: wrap;
}
.stat {
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 6px;
  min-width: 120px;
}
.stat .label {
  font-size: 0.85em;
  color: #909399;
}
.stat .value {
  font-size: 1.6em;
  display: block;
  margin-top: 4px;
}
.text-green { color: #67c23a; }
.text-yellow { color: #e6a23c; }
.text-grey { color: #909399; }

.queue-section h2 {
  font-size: 1.2em;
  margin: 0 0 12px;
}
.empty {
  color: #909399;
  padding: 24px;
  text-align: center;
  background: #f5f7fa;
  border-radius: 6px;
}
table {
  width: 100%;
  border-collapse: collapse;
  background: #fff;
}
th, td {
  padding: 10px 12px;
  border-bottom: 1px solid #ebeef5;
  text-align: left;
  vertical-align: middle;
}
th {
  background: #fafafa;
  font-weight: 600;
  color: #606266;
}
.concept { font-weight: 500; }
.concept-id { font-size: 0.78em; color: #909399; font-family: monospace; }
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 0.78em;
  font-weight: 500;
}
.badge.cycle { background: #fdf6ec; color: #e6a23c; }
.badge.low_conf { background: #f0f9eb; color: #67c23a; }

button {
  padding: 4px 10px;
  border-radius: 4px;
  border: 1px solid #dcdfe6;
  cursor: pointer;
  font-size: 0.9em;
  margin-right: 4px;
}
button.ok { background: #f0f9eb; color: #67c23a; border-color: #c2e7b0; }
button.bad { background: #fef0f0; color: #f56c6c; border-color: #fbc4c4; }
button:hover:not(:disabled) { filter: brightness(0.96); }
</style>