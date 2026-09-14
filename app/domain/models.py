from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator


class Category(StrEnum):
    ALGORITHMS = "Quantum Algorithms"
    ERROR_CORRECTION = "Quantum Error Correction"
    HARDWARE = "Quantum Hardware"
    MEASUREMENT = "Quantum Measurement and Sensing"
    SIMULATION = "Quantum Simulation"


class Paper(BaseModel):
    arxiv_id: str
    version: int = Field(ge=1)
    title: str
    authors: list[str]
    abstract: str
    submitted_at: datetime
    updated_at: datetime
    primary_arxiv_category: str = "quant-ph"
    all_arxiv_categories: list[str] = ["quant-ph"]
    quantumlistener_primary_category: Category | None = None
    quantumlistener_secondary_categories: list[Category] = []
    classification_confidence: float | None = Field(default=None, ge=0, le=1)
    classification_explanation: str | None = None
    pdf_url: HttpUrl
    abstract_url: HttpUrl
    doi: str | None = None
    journal_reference: str | None = None
    comment: str | None = None
    ingestion_run_id: str
    retrieved_at: datetime


class Claim(BaseModel):
    text: str
    label: Literal["Metadata fact", "Author-reported claim", "QuantumListener inference"]
    evidence: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def claims_are_attributed(self):
        if self.label == "Author-reported claim" and not any(
            phrase in self.text.lower()
            for phrase in ("authors report", "paper proposes", "authors propose")
        ):
            raise ValueError("author-reported claims require explicit attribution")
        return self


class PaperSummary(BaseModel):
    arxiv_id: str
    takeaway: str
    accessible_summary: str
    technical_summary: str
    methods: list[str]
    main_result: str
    claimed_advancement: str
    limitations: str
    keywords: list[str] = Field(min_length=3, max_length=3)
    audience: Literal["student", "researcher", "general technical"]
    source_url: HttpUrl
    claims: list[Claim]


class Chapter(BaseModel):
    category: Category
    title: str
    start_seconds: int = Field(ge=0)
    paper_ids: list[str]


class Episode(BaseModel):
    week: str
    title: str
    description: str
    interval_start: datetime
    interval_end: datetime
    duration_seconds: int
    published_at: datetime | None = None
    status: Literal["draft", "approved", "published"] = "draft"
    audio_url: str | None = None
    transcript_url: str | None = None
    show_notes_url: str | None = None
    chapters: list[Chapter]
    paper_ids: list[str]
    main_audio_covers_all: bool = True
