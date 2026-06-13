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
