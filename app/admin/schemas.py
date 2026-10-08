from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SubscriptionStatus = Literal["Free", "Standart", "Pro", "Premium"]


def _empty_to_none(value):
    return None if value == "" else value


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    is_admin: bool
    subscribe_status: str
    date_start: datetime | None = None
    date_end: datetime | None = None
    token_today: int
    created_at: datetime | None = None


class UserPage(BaseModel):
    users: list[UserOut]
    total: int
    page: int
    per_page: int
    total_pages: int


class UserUpdate(BaseModel):
    email: str | None = Field(None, max_length=255)
    password: str | None = Field(None, max_length=256)
    subscribe_status: SubscriptionStatus | None = None
    date_end: date | None = None
    token_today: int | None = Field(None, ge=0)
    is_admin: bool | None = None

    normalize_blank = field_validator("date_end", "password", mode="before")(_empty_to_none)


class UserCreate(BaseModel):
    email: str = Field(max_length=255)
    password: str = Field(max_length=256)
    subscribe_status: SubscriptionStatus = "Free"
    date_end: date | None = None
    token_today: int = Field(0, ge=0)
    is_admin: bool = False

    normalize_blank = field_validator("date_end", mode="before")(_empty_to_none)


class PromoIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    type: str = Field(min_length=1, max_length=50)
    status: bool = True
    date_ended: datetime | None = None
    count_activated: int = Field(0, ge=0)
    bonus_count: int = Field(0, ge=0)
    description: str | None = Field(None, max_length=1000)

    normalize_blank = field_validator("date_ended", "description", mode="before")(_empty_to_none)

    @field_validator("count_activated", "bonus_count", mode="before")
    @classmethod
    def _nan_to_zero(cls, value):
        return 0 if value in (None, "") else value


class PromoOut(PromoIn):
    model_config = ConfigDict(from_attributes=True)
    id: int


class TariffIn(BaseModel):
    price: int = Field(ge=0)
    token_in_day: int | None = Field(None, ge=0)
    sale: bool = False
    new_price: int = Field(0, ge=0)


class PlatformStatusIn(BaseModel):
    enabled: bool
