from datetime import date, datetime

from pydantic import BaseModel


class StudyPlanCreate(BaseModel):
    phase: str
    focus: str | None = None
    start_date: date
    end_date: date
    daily_tasks: str | None = None


class StudyPlanResponse(BaseModel):
    id: int
    user_id: int
    phase: str
    focus: str | None = None
    start_date: date
    end_date: date
    daily_tasks: str | None = None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class StudyRecordCreate(BaseModel):
    subject: str
    knowledge_point_id: int | None = None
    question_id: int | None = None
    is_correct: bool | None = None
    duration_seconds: int = 0
    emotion_score: float | None = None


class StudyRecordResponse(BaseModel):
    id: int
    user_id: int
    subject: str
    knowledge_point_id: int | None = None
    is_correct: bool | None = None
    duration_seconds: int
    emotion_score: float | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class KnowledgePointResponse(BaseModel):
    id: int
    code: str
    name: str
    subject: str
    parent_id: int | None = None
    level: int
    sort_order: int
    applicable_variants: str | None = None
    exam_frequency: int
    difficulty: int

    model_config = {"from_attributes": True}


class KnowledgePointTree(BaseModel):
    id: int | None = None
    code: str | None = None
    name: str
    level: int
    children: list["KnowledgePointTree"] = []

    model_config = {"from_attributes": True}


class QuestionGroupResponse(BaseModel):
    id: int
    subject: str
    title: str | None = None
    content: str
    images: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class QuestionCreate(BaseModel):
    question_type: str
    subject: str
    exam_variant: str | None = None
    knowledge_point_id: int | None = None
    group_id: int | None = None
    group_order: int | None = None
    stem: str
    options: str
    correct_answer: str
    explanation: str | None = None
    difficulty: int = 1
    images: str | None = None


class QuestionResponse(BaseModel):
    id: int
    question_type: str
    subject: str
    exam_variant: str | None = None
    knowledge_point_id: int | None = None
    group_id: int | None = None
    group_order: int | None = None
    stem: str
    options: str
    explanation: str | None = None
    difficulty: int
    images: str | None = None
    knowledge_point: KnowledgePointResponse | None = None
    group: QuestionGroupResponse | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AnswerSubmit(BaseModel):
    answer: str
    duration_seconds: int = 0
    subject: str


class AnswerResult(BaseModel):
    is_correct: bool
    correct_answer: str
    explanation: str | None = None
    record: StudyRecordResponse
