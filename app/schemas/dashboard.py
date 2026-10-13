"""Queries and results for the web console's read endpoints (/dashboard/...)."""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

PatientSource = Literal["all", "voice", "api"]
PatientSort = Literal["newest", "oldest", "name", "name_desc"]
CallOutcome = Literal["all", "registered", "not_registered"]


class PatientListQuery(BaseModel):
    q: str | None = Field(default=None, max_length=100)
    source: PatientSource = "all"
    sort: PatientSort = "newest"
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class CallListQuery(BaseModel):
    q: str | None = Field(default=None, max_length=100)
    outcome: CallOutcome = "all"
    limit: int = Field(default=25, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


@dataclass(frozen=True)
class Page:
    """One page of results plus the number of rows matching the query overall."""

    items: list
    total: int
