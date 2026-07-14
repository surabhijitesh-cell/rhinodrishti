"""User model for authentication."""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from datetime import datetime, timezone
import uuid


class UserCreate(BaseModel):
    username: str
    email: str = ""
    password: str
    name: str = ""
    role: str = "viewer"  # admin, analyst, viewer
    iod: Optional[str] = None  # IOD-1 | IOD-4 | IOD-5 | IOD-CIJ — defaults to IOD-1 if omitted


class UserLogin(BaseModel):
    username: str  # accepts username OR email
    password: str


class UserUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    iod: Optional[str] = None


class PasswordReset(BaseModel):
    new_password: str


class UserInDB(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    username: str
    email: str = ""
    password_hash: str
    name: str = ""
    role: str = "viewer"
    iod: str = "IOD-1"
    is_active: bool = True
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_login: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    username: str
    email: str = ""
    name: str = ""
    role: str
    is_active: bool
    created_at: str
    last_login: Optional[str] = None
