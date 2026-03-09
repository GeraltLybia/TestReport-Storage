from pydantic import BaseModel


class HistoryInfo(BaseModel):
    records: int
    updated_at: str | None
    size: int
