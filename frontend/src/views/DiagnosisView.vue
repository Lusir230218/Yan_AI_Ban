<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import AppLayout from '@/components/AppLayout.vue'

const auth = useAuthStore()

const targetSchool = ref('')
const targetMajor = ref('')
const currentLevel = ref('')
const availableHours = ref<number | null>(null)
const learningStyle = ref('')
const saving = ref(false)
const saved = ref(false)

onMounted(async () => {
  if (!auth.user) await auth.fetchUser()
  if (auth.user) {
    targetSchool.value = auth.user.target_school || ''
    targetMajor.value = auth.user.target_major || ''
    currentLevel.value = auth.user.current_level || ''
    availableHours.value = auth.user.available_hours
    learningStyle.value = auth.user.learning_style || ''
  }
})

async function handleSave() {
  saving.value = true
  saved.value = false
  try {
    await auth.updateDiagnosis({
      target_school: targetSchool.value || null,
      target_major: targetMajor.value || null,
      current_level: currentLevel.value || null,
      available_hours: availableHours.value,
      learning_style: learningStyle.value || null,
    })
    saved.value = true
    setTimeout(() => (saved.value = false), 3000)
  } finally {
    saving.value = false
  }
}

const levelOptions = ['一本', '二本', '三本/民办', '专科', '已毕业']
const styleOptions = ['阅读笔记', '听课视频', '刷题练习', '综合']
</script>

<template>
  <AppLayout>
    <div class="diagnosis-page">
      <div class="form-card">
        <div class="form-header">
          <h2>考研画像</h2>
          <p>完善信息以便为你推荐更精准的学习方案</p>
        </div>

        <form @submit.prevent="handleSave" class="form-body">
          <div v-if="saved" class="msg success">保存成功！</div>

          <div class="form-grid">
            <div class="field">
              <label>目标院校</label>
              <input v-model="targetSchool" placeholder="例：北京大学" />
            </div>
            <div class="field">
              <label>目标专业</label>
              <input v-model="targetMajor" placeholder="例：计算机科学与技术" />
            </div>
            <div class="field">
              <label>当前学历</label>
              <select v-model="currentLevel">
                <option value="">请选择</option>
                <option v-for="opt in levelOptions" :key="opt" :value="opt">{{ opt }}</option>
              </select>
            </div>
            <div class="field">
              <label>每日可用学习时长（小时）</label>
              <input v-model.number="availableHours" type="number" min="1" max="24" placeholder="例：8" />
            </div>
          </div>

          <div class="field">
            <label>偏好学习方式</label>
            <div class="radio-group">
              <label v-for="opt in styleOptions" :key="opt" class="radio-item">
                <input v-model="learningStyle" type="radio" :value="opt" />
                <span>{{ opt }}</span>
              </label>
            </div>
          </div>

          <div class="form-actions">
            <button type="submit" class="btn-primary" :disabled="saving">
              {{ saving ? '保存中...' : '保存画像' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </AppLayout>
</template>

<style scoped>
.diagnosis-page {
  max-width: 720px;
}
.form-card {
  background: #fff;
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.06);
}
.form-header {
  padding: 20px 24px;
  border-bottom: 1px solid #f3f4f6;
}
.form-header h2 {
  font-size: 18px;
  font-weight: 600;
  margin: 0 0 4px;
}
.form-header p {
  color: #6b7280;
  font-size: 14px;
  margin: 0;
}
.form-body {
  padding: 24px;
}
.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px 20px;
  margin-bottom: 16px;
}
.field label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: #374151;
  margin-bottom: 6px;
}
.field input,
.field select {
  width: 100%;
  padding: 9px 12px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  font-size: 15px;
  outline: none;
  box-sizing: border-box;
  transition: border-color 0.2s;
}
.field input:focus,
.field select:focus {
  border-color: #4f46e5;
  box-shadow: 0 0 0 3px rgba(79, 70, 229, 0.1);
}
.radio-group {
  display: flex;
  gap: 16px;
  flex-wrap: wrap;
}
.radio-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 14px;
  cursor: pointer;
  padding: 6px 0;
}
.form-actions {
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid #f3f4f6;
}
.btn-primary {
  padding: 10px 28px;
  background: #4f46e5;
  color: #fff;
  border: none;
  border-radius: 8px;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-primary:hover {
  background: #4338ca;
}
.btn-primary:disabled {
  background: #a5b4fc;
  cursor: not-allowed;
}
.msg.success {
  background: #f0fdf4;
  color: #16a34a;
  padding: 10px 14px;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 14px;
}
</style>
