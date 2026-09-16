from datetime import datetime
from pydantic import BaseModel, Field


class MemberCreate(BaseModel):
    display_name: str = Field(..., max_length=50, description="显示名")
    relation: str = Field(..., max_length=20, description="关系（本人/配偶/子女/父母/其他）")
    birth_year: int | None = Field(default=None, description="出生年份")
    gender: str | None = Field(default=None, description="性别")
    occupation: str | None = Field(default=None, description="职业描述")
    city: str | None = Field(default=None, description="所在城市")
    social_insurance: str | None = Field(default="未知", description="社保类型（职工/居民/无/未知）")
    color: str = Field(default="#2A8F82", description="头像颜色")
    real_name: str | None = Field(default=None, description="真实姓名（仅本地加密存储，用于脱敏）")


class MemberUpdate(BaseModel):
    display_name: str | None = None
    relation: str | None = None
    birth_year: int | None = None
    gender: str | None = None
    occupation: str | None = None
    city: str | None = None
    social_insurance: str | None = None
    color: str | None = None
    real_name: str | None = None


class MemberResponse(BaseModel):
    id: str
    display_name: str
    relation: str
    birth_year: int | None
    gender: str | None
    occupation: str | None
    city: str | None
    social_insurance: str | None
    color: str
    placeholder: str
    real_name: str | None = None
    created_at: datetime | None = None

    model_config = {"from_attributes": True}

