from pydantic import BaseModel, HttpUrl
from typing import Optional
from datetime import datetime

# Схемы для пользователей
class UserCreate(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    is_active: bool
    created_at: datetime

    class Config:
        orm_mode = True

# Схема для токена
class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None

# Схемы для ссылок
class LinkBase(BaseModel):
    original_url: HttpUrl
    custom_alias: Optional[str] = None
    expires_at: Optional[datetime] = None

class LinkCreate(LinkBase):
    pass

class LinkUpdate(BaseModel):
    original_url: Optional[HttpUrl] = None
    expires_at: Optional[datetime] = None

class LinkResponse(LinkBase):
    id: int
    short_code: str
    created_at: datetime
    last_accessed: Optional[datetime] = None
    access_count: int
    user_id: Optional[int] = None

    class Config:
        orm_mode = True

class LinkStats(BaseModel):
    original_url: HttpUrl
    created_at: datetime
    last_accessed: Optional[datetime] = None
    access_count: int
    expires_at: Optional[datetime] = None
