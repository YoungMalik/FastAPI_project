from pydantic import BaseModel, EmailStr, HttpUrl
from datetime import datetime
from typing import Optional

class UserBase(BaseModel):
    email: EmailStr

class UserCreate(UserBase):
    password: str

class User(UserBase):
    id: int
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class LinkBase(BaseModel):
    original_url: HttpUrl
    custom_alias: Optional[str] = None
    expires_at: Optional[datetime] = None

class LinkCreate(LinkBase):
    pass

class Link(LinkBase):
    id: int
    short_code: str
    created_at: datetime
    last_accessed: Optional[datetime]
    access_count: int
    user_id: Optional[int]

    class Config:
        from_attributes = True

class LinkStats(BaseModel):
    original_url: HttpUrl
    created_at: datetime
    last_accessed: Optional[datetime]
    access_count: int
    expires_at: Optional[datetime]

    class Config:
        from_attributes = True

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    email: Optional[str] = None