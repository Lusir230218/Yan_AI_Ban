from datetime import datetime

from pydantic import BaseModel, Field


class UserRegister(BaseModel):
    phone: str = Field(max_length=20)
    password: str = Field(min_length=6, max_length=100)
    nickname: str = Field(max_length=50)


class UserLogin(BaseModel):
    phone: str
    password: str


class UserDiagnosis(BaseModel):
    target_school: str | None = None
    target_major: str | None = None
    current_level: str | None = None
    available_hours: int | None = None
    learning_style: str | None = None


class UserResponse(BaseModel):
    id: int
    phone: str
    nickname: str
    avatar: str | None = None
    target_school: str | None = None
    target_major: str | None = None
    current_level: str | None = None
    available_hours: int | None = None
    learning_style: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
