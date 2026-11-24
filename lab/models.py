from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, FiniteFloat, model_validator


class Segment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
    route_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
    from_measure_mi: FiniteFloat = Field(strict=True, ge=0)
    to_measure_mi: FiniteFloat = Field(strict=True)
    geometry: dict
    functional_class: Literal["Interstate", "Principal arterial", "Minor arterial", "Collector"]
    lanes: int = Field(strict=True, ge=1, le=12)
    surface: Literal["Asphalt", "Concrete", "Gravel"]
    aadt: int = Field(strict=True, ge=0)
    effective_date: date
    modified_at: datetime
    dataset_version: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")

    @model_validator(mode="after")
    def ordered_interval(self):
        if self.to_measure_mi <= self.from_measure_mi:
            raise ValueError("End milepoint must exceed start milepoint")
        return self
