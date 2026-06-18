export interface UserRegister {
  phone: string
  password: string
  nickname: string
}

export interface UserLogin {
  phone: string
  password: string
}

export interface Token {
  access_token: string
  token_type: string
}

export interface UserResponse {
  id: number
  phone: string
  nickname: string
  avatar: string | null
  target_school: string | null
  target_major: string | null
  current_level: string | null
  available_hours: number | null
  learning_style: string | null
  created_at: string
}

export interface UserDiagnosis {
  target_school?: string | null
  target_major?: string | null
  current_level?: string | null
  available_hours?: number | null
  learning_style?: string | null
}

export interface StudyPlanCreate {
  phase: string
  focus?: string | null
  start_date: string
  end_date: string
  daily_tasks?: string | null
}

export interface StudyPlanResponse {
  id: number
  user_id: number
  phase: string
  focus: string | null
  start_date: string
  end_date: string
  daily_tasks: string | null
  status: string
  created_at: string
}

export interface StudyRecordCreate {
  subject: string
  knowledge_point_id?: number | null
  question_id?: number | null
  is_correct?: boolean | null
  duration_seconds: number
  emotion_score?: number | null
}

export interface StudyRecordResponse {
  id: number
  user_id: number
  subject: string
  knowledge_point_id: number | null
  is_correct: boolean | null
  duration_seconds: number
  emotion_score: number | null
  created_at: string
}

export interface KnowledgePointResponse {
  id: number
  code: string
  name: string
  subject: string
  parent_id: number | null
  level: number
  sort_order: number
  exam_frequency: number
  difficulty: number
}

export interface KnowledgePointTree {
  id: number | null
  code: string | null
  name: string
  level: number
  children: KnowledgePointTree[]
}

export interface QuestionGroupResponse {
  id: number
  subject: string
  title: string | null
  content: string
  images: string | null
  created_at: string
}

export interface QuestionResponse {
  id: number
  question_type: string
  subject: string
  exam_variant: string | null
  knowledge_point_id: number | null
  group_id: number | null
  group_order: number | null
  stem: string
  options: string
  explanation: string | null
  difficulty: number
  images: string | null
  knowledge_point: KnowledgePointResponse | null
  group: QuestionGroupResponse | null
  created_at: string
}

export interface AnswerSubmit {
  answer: string
  duration_seconds: number
  subject: string
}

export interface AnswerResult {
  is_correct: boolean
  correct_answer: string
  explanation: string | null
  record: StudyRecordResponse
}

export interface QuestionCreate {
  question_type: string
  subject: string
  exam_variant?: string | null
  knowledge_point_id?: number | null
  group_id?: number | null
  group_order?: number | null
  stem: string
  options: string
  correct_answer: string
  explanation?: string | null
  difficulty?: number
  images?: string | null
}
