from datetime import datetime, date
from pydantic import BaseModel, field_validator
from typing import Optional


class UserUpdate(BaseModel):
    email: Optional[str] = None
    subscribe_status: Optional[str] = None
    date_end: Optional[date] = None
    token_today: Optional[int] = None
    is_admin: Optional[bool] = None

    @field_validator('date_end', mode='before')
    def parse_date(cls, value):
        if isinstance(value, str):
            try:
                return datetime.strptime(value, "%Y-%m-%d").date()
            except ValueError:
                raise ValueError("Invalid date format. Use YYYY-MM-DD")
        return value