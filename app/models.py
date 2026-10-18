"""
Pydantic models matching every schema in Section 5 of the build spec.
"""

from __future__ import annotations
from typing import Optional
from pydantic import BaseModel, Field


# ── Raw scrape outputs ─────────────────────────────────────────────

class LinkedInExperience(BaseModel):
    title: str = ""
    company: str = ""
    description: str = ""


class LinkedInEducation(BaseModel):
    school: str = ""
    degree: str = ""


class RawLinkedIn(BaseModel):
    url: str = ""
    name: str = ""
    headline: str = ""
    about: str = ""
    location: str = ""
    experience: list[LinkedInExperience] = Field(default_factory=list)
    education: list[LinkedInEducation] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    posts: list[str] = Field(default_factory=list)


class InstagramPost(BaseModel):
    caption: str = ""
    hashtags: list[str] = Field(default_factory=list)
    location: str = ""
    likes: int = 0
    timestamp: str = ""


class RawInstagram(BaseModel):
    url: str = ""
    username: str = ""
    full_name: str = ""
    bio: str = ""
    is_private: bool = False
    followers: int = 0
    following: int = 0
    posts: list[InstagramPost] = Field(default_factory=list)


# ── Person ─────────────────────────────────────────────────────────

class Person(BaseModel):
    id: str  # slug
    name: str
    linkedin_url: str = ""
    instagram_url: str = ""
    status: str = "ok"  # ok | partial | failed
    warnings: list[str] = Field(default_factory=list)


# ── Profile (LLM output) ──────────────────────────────────────────

class EvidencedItem(BaseModel):
    item: str
    evidence: str


class CommunicationStyle(BaseModel):
    description: str = ""
    evidence: str = ""


class LookingFor(BaseModel):
    description: str = ""
    confidence: str = "low"  # low | medium | high
    evidence: str = ""


class Lifestyle(BaseModel):
    description: str = ""
    evidence: str = ""


class DataQuality(BaseModel):
    linkedin: str = "none"  # none | thin | rich
    instagram: str = "none"  # none | thin | rich


class Profile(BaseModel):
    id: str
    summary: str = ""
    needs: list[EvidencedItem] = Field(default_factory=list)
    hobbies: list[EvidencedItem] = Field(default_factory=list)
    interests: list[EvidencedItem] = Field(default_factory=list)
    values: list[EvidencedItem] = Field(default_factory=list)
    communication_style: CommunicationStyle = Field(default_factory=CommunicationStyle)
    personality_signals: list[EvidencedItem] = Field(default_factory=list)
    looking_for: LookingFor = Field(default_factory=LookingFor)
    dealbreakers: list[EvidencedItem] = Field(default_factory=list)
    lifestyle: Lifestyle = Field(default_factory=Lifestyle)
    agent_persona: str = ""
    data_quality: DataQuality = Field(default_factory=DataQuality)
    model_used: str = ""


# ── Date result ────────────────────────────────────────────────────

class TranscriptTurn(BaseModel):
    speaker: str  # "a" or "b"
    text: str


class Verdict(BaseModel):
    score: int = 0
    chemistry: str = ""
    concerns: str = ""
    would_second_date: bool = False


class DateResult(BaseModel):
    a: str  # person id
    b: str  # person id
    transcript: list[TranscriptTurn] = Field(default_factory=list)
    a_verdict: Verdict = Field(default_factory=Verdict)
    b_verdict: Verdict = Field(default_factory=Verdict)
    final_score: float = 0.0
    date_failed: bool = False
    model_used: str = ""


# ── Ranking ────────────────────────────────────────────────────────

class MatchEntry(BaseModel):
    other_id: str
    score: float = 0.0
    dated: bool = True
    reason: str = ""
    date_ref: str = ""  # e.g. "alice__bob"


class PersonRanking(BaseModel):
    person_id: str
    matches: list[MatchEntry] = Field(default_factory=list)


# ── Job / Run tracking ────────────────────────────────────────────

class ProgressEvent(BaseModel):
    stage: str  # scrape | analyze | shortlist | date | rank | done
    done: int = 0
    total: int = 0
    message: str = ""


class RunState(BaseModel):
    run_id: str
    status: str = "pending"  # pending | running | completed | failed
    people: list[Person] = Field(default_factory=list)
    current_stage: str = ""
    progress: list[ProgressEvent] = Field(default_factory=list)
    error: Optional[str] = None
