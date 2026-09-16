from typing import List, Optional, Dict
from pydantic import BaseModel


class ReminderDto(BaseModel):
    id: str
    policy_id: Optional[str] = None
    member_id: Optional[str] = None
    member_name: Optional[str] = None
    product_name: Optional[str] = None
    kind: str
    due_date: str
    title: str
    content: Optional[str] = None
    status: str
    created_at: str


class CalendarSettingsResponse(BaseModel):
    token: str
    ics_url: str
    enabled: bool


class ResetTokenResponse(BaseModel):
    token: str
    ics_url: str


class ReferenceConfigRequest(BaseModel):
    member_id: str
    references: Dict[str, int]  # category -> amount in yuan


class ReferenceConfigResponse(BaseModel):
    references: Dict[str, Dict[str, int]]  # member_id -> category -> amount in yuan
