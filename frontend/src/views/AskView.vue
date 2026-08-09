<script setup lang="ts">
/**
 * 阶段五·2C: 知识问答页 — 包装 AIChatPanel。
 *
 * 路由 /ask 独立页面；区别于 /ai-solve（单题解答）和 /tutoring（多模态辅导），
 * 这里走知识图谱检索 + 引用 chip + 👍/👎。
 */
import AppLayout from '@/components/AppLayout.vue'
import AIChatPanel from '@/components/AIChatPanel.vue'
import { Message } from '@element-plus/icons-vue'
</script>

<template>
  <AppLayout>
    <div class="ask-page">
      <div class="ask-intro">
        <el-icon :size="20" color="#4a90e2"><Message /></el-icon>
        <span>基于知识图谱的问答 — 回答末尾的 [引用] 可点开看概念定义</span>
      </div>
      <AIChatPanel />
    </div>
  </AppLayout>
</template>

<style scoped>
.ask-page { max-width: 900px; margin: 0 auto; display: flex; flex-direction: column; gap: 16px; }
.ask-intro {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 14px; background: #eef6ff; border-radius: 8px;
  font-size: 13px; color: #4a90e2;
}
</style>