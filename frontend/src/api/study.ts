import client from './client'
import type { StudyPlanCreate, StudyPlanResponse, StudyRecordCreate, StudyRecordResponse } from '@/types'

export const studyApi = {
  createPlan(data: StudyPlanCreate) {
    return client.post<StudyPlanResponse>('/study/plans', data)
  },
  generatePlans() {
    return client.post<StudyPlanResponse[]>('/study/generate-plans')
  },
  listPlans() {
    return client.get<StudyPlanResponse[]>('/study/plans')
  },
  createRecord(data: StudyRecordCreate) {
    return client.post<StudyRecordResponse>('/study/records', data)
  },
  listRecords() {
    return client.get<StudyRecordResponse[]>('/study/records')
  },
}
