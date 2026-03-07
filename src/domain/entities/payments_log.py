from datetime import date, datetime
from enum import Enum
from typing import Optional
from bson import ObjectId
from pydantic import BaseModel, Field


class UserGrade(str, Enum):
    ONE_DIARY_ONE_DAY = "one diary one day"


class PaymentsLog(BaseModel):
    id: str = Field(default_factory=lambda: str(ObjectId()))
    pay_date: datetime = Field(default_factory=datetime.now)
    grade: UserGrade = Field(default=UserGrade.ONE_DIARY_ONE_DAY)
    user_id: str
    start_date: date
    end_date: date
    price: int
    log: Optional[str]
