from datetime import datetime

from pydantic import BaseModel


class TutorMessage(BaseModel):
    role: str
    content: str
    round: int
    hint_level: int
    created_at: datetime | None = None


class TutorContinueRequest(BaseModel):
    user_input: str


class TutorSessionResponse(BaseModel):
    id: int
    user_id: int
    question_id: int | None = None
    current_round: int
    hint_level: int
    status: str
    messages: list[dict] = []
    created_at: datetime

    model_config = {"from_attributes": True}


class TutorContinueResponse(BaseModel):
    session_id: int
    message: str
    current_round: int
    hint_level: int
    status: str


class TutorSessionListItem(BaseModel):
    id: int
    question_id: int | None = None
    current_round: int
    hint_level: int
    status: str
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime
