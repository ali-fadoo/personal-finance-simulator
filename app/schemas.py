from pydantic import BaseModel

from pydantic import BaseModel, field_validator
import re
from datetime import datetime

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

class TransactionCreate(BaseModel):
    amount: float
    category: str
    date: str  # stored as YYYY-MM-DD internally

    @field_validator("date")
    @classmethod
    def normalize_date(cls, v: str) -> str:
        # Accept common separators
        v = v.strip()

        # Replace / or . with -
        v = re.sub(r"[/.]", "-", v)

        try:
            # Validate + normalize
            dt = datetime.strptime(v, "%Y-%m-%d")
        except ValueError:
            raise ValueError(
                "date must be in YYYY-MM-DD, YYYY/MM/DD, or YYYY.MM.DD format"
            )

        # Always store in canonical format
        return dt.strftime("%Y-%m-%d")

    @field_validator("category")
    @classmethod
    def normalize_category(cls, v: str) -> str:
        v = v.strip().lower()
        if not v:
            raise ValueError("category cannot be empty")
        return v


class TransactionOut(TransactionCreate):
    id: int

    class Config:
        from_attributes = True
